from __future__ import annotations

import base64
import binascii
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from ..errors import ApiError
from ..settings import (
    SAM3_BACKEND_SCRIPT,
    SAM3_PYTHON,
    SAM3D_OBJECTS_BACKEND_SCRIPT,
    SAM3D_OBJECTS_PYTHON,
)
from ..schemas import (
    ObservationPayload,
    ObservationResult,
    PerceptionRequest,
    PerceptionResponse,
    Sam3BackendPayload,
    Sam3DetectionPayload,
    SceneArtifacts,
)
from .artifact_store import ArtifactStore
from .backend_runner import BackendCommand
from .pointmap import (
    depth_to_pointmap,
    load_depth_meters,
    load_rgb_size,
)


_SLUG_RE = re.compile(r"[^a-zA-Z0-9]+")


@dataclass(slots=True)
class Sam3ObservationSummary:
    transport_status: str
    backend_status: str
    detections: list[dict[str, Any]]
    matched_object_texts: list[str]
    mask_artifact_ids: list[str]
    error_message: str | None = None


class PerceptionInferenceService:
    def __init__(self, artifact_store: ArtifactStore) -> None:
        self.artifact_store = artifact_store
        self.sam3_backend = BackendCommand(
            name="sam3",
            python_path=SAM3_PYTHON,
            script_path=SAM3_BACKEND_SCRIPT,
        )
        self.sam3d_backend = BackendCommand(
            name="sam3d_objects",
            python_path=SAM3D_OBJECTS_PYTHON,
            script_path=SAM3D_OBJECTS_BACKEND_SCRIPT,
        )

    def infer(self, request: PerceptionRequest) -> PerceptionResponse:
        request_id = self._build_request_id()
        backend_status = self._collect_backend_status(request_id=request_id)
        observation_results = [
            self._infer_observation(
                request_id=request_id,
                request=request,
                observation=observation,
                observation_index=index,
                backend_status=backend_status,
            )
            for index, observation in enumerate(request.observations)
        ]

        requested_object_texts = list(dict.fromkeys(request.task.object_texts))
        matched_object_texts = self._collect_matched_object_texts(observation_results)
        unmatched_object_texts = [
            object_text
            for object_text in requested_object_texts
            if object_text not in matched_object_texts
        ]
        pointmap_generated_camera_ids = [
            result.camera_id
            for result in observation_results
            if bool(result.ext.get("pointmap_generated"))
        ]
        sam3_candidate_camera_ids = [
            result.camera_id
            for result in observation_results
            if int(result.ext.get("sam3_candidate_count", 0)) > 0
        ]
        sam3_candidate_total = sum(
            int(result.ext.get("sam3_candidate_count", 0))
            for result in observation_results
        )
        success = any(result.success for result in observation_results)

        return PerceptionResponse(
            request_id=request_id,
            success=success,
            timestamp=datetime.now(timezone.utc),
            observation_results=observation_results,
            error={} if success else self._build_response_error(sam3_candidate_total),
            ext={
                "matched_object_texts": matched_object_texts,
                "unmatched_object_texts": unmatched_object_texts,
                "processed_camera_ids": [
                    observation.camera_id for observation in request.observations
                ],
                "pointmap_generated_camera_ids": pointmap_generated_camera_ids,
                "sam3_candidate_camera_ids": sam3_candidate_camera_ids,
                "sam3_candidate_total": sam3_candidate_total,
                "backend_status": backend_status,
            },
        )

    def _infer_observation(
        self,
        *,
        request_id: str,
        request: PerceptionRequest,
        observation: ObservationPayload,
        observation_index: int,
        backend_status: dict[str, Any],
    ) -> ObservationResult:
        rgb_metadata = self.artifact_store.get_metadata(observation.rgb_image.artifact_id)
        depth_metadata = self.artifact_store.get_metadata(observation.depth_image.artifact_id)

        self._assert_artifact_type(
            rgb_metadata.artifact_type,
            "rgb_image",
            rgb_metadata.artifact_id,
        )
        self._assert_artifact_type(
            depth_metadata.artifact_type,
            "depth_image",
            depth_metadata.artifact_id,
        )

        rgb_path = self.artifact_store.get_content_path(rgb_metadata.artifact_id)
        depth_path = self.artifact_store.get_content_path(depth_metadata.artifact_id)

        rgb_width, rgb_height = load_rgb_size(rgb_metadata, rgb_path)
        intrinsics = observation.intrinsics
        if rgb_width != intrinsics.width or rgb_height != intrinsics.height:
            raise ApiError(
                status_code=400,
                error_code="INVALID_REQUEST",
                message="RGB resolution does not match observations[].intrinsics.",
                ext={
                    "details": {
                        "camera_id": observation.camera_id,
                        "artifact_id": rgb_metadata.artifact_id,
                        "actual_width": rgb_width,
                        "actual_height": rgb_height,
                        "expected_width": intrinsics.width,
                        "expected_height": intrinsics.height,
                    }
                },
            )

        depth_m = load_depth_meters(
            depth_metadata,
            depth_path,
            depth_scale_m_per_unit=observation.depth_scale_m_per_unit,
        )
        pointmap_result = depth_to_pointmap(depth_m, intrinsics)
        sam3_summary = self._run_sam3_inference(
            request_id=request_id,
            request=request,
            observation=observation,
            observation_index=observation_index,
            rgb_path=rgb_path,
        )

        debug_artifact_ids: list[str] = []
        if request.options.include_debug_artifacts:
            debug_payload = self._build_debug_payload(
                request_id=request_id,
                request=request,
                observation=observation,
                observation_index=observation_index,
                pointmap_result=pointmap_result,
                backend_status=backend_status,
                sam3_summary=sam3_summary,
            )
            debug_metadata = self.artifact_store.save_bytes(
                artifact_type="debug_json",
                filename=f"{request_id}_obs_{observation_index:02d}_preflight.json",
                content_type="application/json",
                data=json.dumps(debug_payload, ensure_ascii=True, indent=2).encode("utf-8"),
                ext={"camera_id": observation.camera_id},
            )
            debug_artifact_ids.append(debug_metadata.artifact_id)

        return ObservationResult(
            camera_id=observation.camera_id,
            observation_timestamp=observation.timestamp,
            success=False,
            coordinate_frame="camera",
            detected_objects=[],
            scene_artifacts=SceneArtifacts(
                visualization_artifact_ids=[],
                debug_artifact_ids=debug_artifact_ids,
            ),
            error=self._build_observation_error(sam3_summary),
            ext={
                "pointmap_generated": True,
                "sam3_transport_status": sam3_summary.transport_status,
                "sam3_backend_status": sam3_summary.backend_status,
                "sam3_candidate_count": len(sam3_summary.detections),
                "sam3_mask_artifact_ids": sam3_summary.mask_artifact_ids,
                "sam3_matched_object_texts": sam3_summary.matched_object_texts,
                "sam3_detections": sam3_summary.detections,
                "sam3_error_message": sam3_summary.error_message,
            },
        )

    def _run_sam3_inference(
        self,
        *,
        request_id: str,
        request: PerceptionRequest,
        observation: ObservationPayload,
        observation_index: int,
        rgb_path: Any,
    ) -> Sam3ObservationSummary:
        payload = {
            "request_id": request_id,
            "mode": "infer",
            "observation_index": observation_index,
            "image_path": str(rgb_path),
            "object_texts": list(request.task.object_texts),
            "max_objects_per_label": request.options.max_objects_per_label,
        }
        raw_result = self.sam3_backend.invoke_json(payload)
        transport_status = str(raw_result.get("status", "invalid"))
        if transport_status != "ok":
            return Sam3ObservationSummary(
                transport_status=transport_status,
                backend_status="transport_error",
                detections=[],
                matched_object_texts=[],
                mask_artifact_ids=[],
                error_message="SAM3 bridge process did not return a usable JSON payload.",
            )

        response_payload = raw_result.get("response")
        if not isinstance(response_payload, dict):
            return Sam3ObservationSummary(
                transport_status=transport_status,
                backend_status="invalid_response",
                detections=[],
                matched_object_texts=[],
                mask_artifact_ids=[],
                error_message="SAM3 bridge response must be a JSON object.",
            )

        try:
            sam3_payload = Sam3BackendPayload.model_validate(response_payload)
        except ValidationError as exc:
            return Sam3ObservationSummary(
                transport_status=transport_status,
                backend_status="invalid_response",
                detections=[],
                matched_object_texts=[],
                mask_artifact_ids=[],
                error_message=f"SAM3 bridge response validation failed: {exc}",
            )

        if sam3_payload.status != "ok":
            return Sam3ObservationSummary(
                transport_status=transport_status,
                backend_status=sam3_payload.status,
                detections=[],
                matched_object_texts=[],
                mask_artifact_ids=[],
                error_message=sam3_payload.error_message,
            )

        detection_summaries: list[dict[str, Any]] = []
        mask_artifact_ids: list[str] = []
        matched_object_texts: list[str] = []
        for detection_index, detection in enumerate(sam3_payload.detections):
            detection_summary = self._summarize_sam3_detection(
                observation=observation,
                observation_index=observation_index,
                detection_index=detection_index,
                detection=detection,
                include_mask_artifacts=request.options.include_mask_artifacts,
            )
            detection_summaries.append(detection_summary)

            mask_artifact_id = detection_summary["source_mask_artifact_id"]
            if isinstance(mask_artifact_id, str):
                mask_artifact_ids.append(mask_artifact_id)

            source_object_text = detection_summary["source_object_text"]
            if isinstance(source_object_text, str) and source_object_text not in matched_object_texts:
                matched_object_texts.append(source_object_text)

        return Sam3ObservationSummary(
            transport_status=transport_status,
            backend_status=sam3_payload.status,
            detections=detection_summaries,
            matched_object_texts=matched_object_texts,
            mask_artifact_ids=mask_artifact_ids,
            error_message=sam3_payload.error_message,
        )

    def _summarize_sam3_detection(
        self,
        *,
        observation: ObservationPayload,
        observation_index: int,
        detection_index: int,
        detection: Sam3DetectionPayload,
        include_mask_artifacts: bool,
    ) -> dict[str, Any]:
        mask_artifact_id: str | None = None
        if include_mask_artifacts and detection.mask_png_base64 is not None:
            try:
                mask_bytes = self._decode_mask_png_bytes(detection.mask_png_base64)
            except ValueError as exc:
                detection_ext = {**detection.ext, "mask_error": str(exc)}
            else:
                filename = self._build_mask_filename(
                    observation_index=observation_index,
                    detection_index=detection_index,
                    source_object_text=detection.source_object_text,
                )
                metadata = self.artifact_store.save_bytes(
                    artifact_type="mask_image",
                    filename=filename,
                    content_type="image/png",
                    data=mask_bytes,
                    ext={
                        "camera_id": observation.camera_id,
                        "label": detection.label,
                        "source_object_text": detection.source_object_text,
                    },
                )
                mask_artifact_id = metadata.artifact_id
                detection_ext = dict(detection.ext)
        else:
            detection_ext = dict(detection.ext)

        return {
            "instance_id": self._build_partial_instance_id(
                camera_id=observation.camera_id,
                source_object_text=detection.source_object_text,
                detection_index=detection_index,
            ),
            "label": detection.label,
            "source_object_text": detection.source_object_text,
            "score": detection.score,
            "source_mask_artifact_id": mask_artifact_id,
            "bbox_2d_xyxy": list(detection.bbox_2d_xyxy),
            "ext": detection_ext,
        }

    @staticmethod
    def _build_partial_instance_id(
        *,
        camera_id: str,
        source_object_text: str,
        detection_index: int,
    ) -> str:
        camera_slug = PerceptionInferenceService._slugify_text(camera_id)
        object_slug = PerceptionInferenceService._slugify_text(source_object_text)
        return f"sam3_{camera_slug}_{object_slug}_{detection_index + 1:04d}"

    @staticmethod
    def _build_mask_filename(
        *,
        observation_index: int,
        detection_index: int,
        source_object_text: str,
    ) -> str:
        object_slug = PerceptionInferenceService._slugify_text(source_object_text)
        return f"obs_{observation_index:02d}_{object_slug}_{detection_index:02d}.png"

    @staticmethod
    def _slugify_text(value: str) -> str:
        slug = _SLUG_RE.sub("_", value.strip()).strip("_").lower()
        return slug or "object"

    @staticmethod
    def _decode_mask_png_bytes(mask_png_base64: str) -> bytes:
        try:
            mask_bytes = base64.b64decode(mask_png_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("mask_png_base64 is not valid base64.") from exc

        try:
            with Image.open(BytesIO(mask_bytes)) as image:
                image.load()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("mask_png_base64 did not decode to a valid PNG image.") from exc
        return mask_bytes

    @staticmethod
    def _collect_matched_object_texts(
        observation_results: list[ObservationResult],
    ) -> list[str]:
        matched_object_texts: list[str] = []
        for observation_result in observation_results:
            raw_values = observation_result.ext.get("sam3_matched_object_texts", [])
            if not isinstance(raw_values, list):
                continue
            for raw_value in raw_values:
                if isinstance(raw_value, str) and raw_value not in matched_object_texts:
                    matched_object_texts.append(raw_value)
        return matched_object_texts

    @staticmethod
    def _build_observation_error(sam3_summary: Sam3ObservationSummary) -> dict[str, str]:
        if sam3_summary.detections:
            return {
                "code": "NOT_IMPLEMENTED",
                "message": "SAM3 produced 2D candidate masks for this observation, but 3D reconstruction is not integrated yet.",
            }
        if sam3_summary.error_message:
            return {
                "code": "INTERNAL_ERROR",
                "message": sam3_summary.error_message,
            }
        return {
            "code": "INTERNAL_ERROR",
            "message": "Inference backends are not producing detections yet for this observation. Request validation and internal pointmap generation completed.",
        }

    @staticmethod
    def _build_response_error(sam3_candidate_total: int) -> dict[str, str]:
        if sam3_candidate_total > 0:
            return {
                "code": "NOT_IMPLEMENTED",
                "message": "SAM3 produced 2D candidate masks for one or more observations, but 3D reconstruction is not integrated yet.",
            }
        return {
            "code": "INTERNAL_ERROR",
            "message": "Inference backends are not producing detections yet. Request validation and internal pointmap generation completed for all observations.",
        }

    @staticmethod
    def _assert_artifact_type(actual: str, expected: str, artifact_id: str) -> None:
        if actual != expected:
            raise ApiError(
                status_code=400,
                error_code="ARTIFACT_TYPE_MISMATCH",
                message="Artifact type does not match request field.",
                ext={
                    "details": {
                        "artifact_id": artifact_id,
                        "expected": expected,
                        "actual": actual,
                    }
                },
            )

    @staticmethod
    def _build_request_id() -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"perc_req_{stamp}_{secrets.token_hex(4)}"

    def _collect_backend_status(self, *, request_id: str) -> dict[str, Any]:
        payload = {"request_id": request_id, "mode": "preflight"}
        return {
            "sam3": self.sam3_backend.invoke_json(payload),
            "sam3d_objects": self.sam3d_backend.invoke_json(payload),
        }

    @staticmethod
    def _build_debug_payload(
        *,
        request_id: str,
        request: PerceptionRequest,
        observation: ObservationPayload,
        observation_index: int,
        pointmap_result: Any,
        backend_status: dict[str, Any],
        sam3_summary: Sam3ObservationSummary,
    ) -> dict[str, Any]:
        extrinsics = None
        if observation.extrinsics is not None:
            extrinsics = observation.extrinsics.model_dump(mode="json")

        return {
            "request_id": request_id,
            "task_id": request.task.task_id,
            "object_texts": list(request.task.object_texts),
            "observation_index": observation_index,
            "observation": {
                "camera_id": observation.camera_id,
                "rgb_image": observation.rgb_image.model_dump(
                    mode="json",
                    exclude_none=True,
                ),
                "depth_image": observation.depth_image.model_dump(
                    mode="json",
                    exclude_none=True,
                ),
                "intrinsics": observation.intrinsics.model_dump(mode="json"),
                "extrinsics": extrinsics,
                "timestamp": observation.timestamp.isoformat(),
                "ext": dict(observation.ext),
            },
            "pointmap": {
                "width": pointmap_result.width,
                "height": pointmap_result.height,
                "valid_fraction": pointmap_result.valid_fraction,
                "min_depth_m": pointmap_result.min_depth_m,
                "max_depth_m": pointmap_result.max_depth_m,
            },
            "backends": backend_status,
            "sam3_summary": {
                "transport_status": sam3_summary.transport_status,
                "backend_status": sam3_summary.backend_status,
                "candidate_count": len(sam3_summary.detections),
                "matched_object_texts": sam3_summary.matched_object_texts,
                "mask_artifact_ids": sam3_summary.mask_artifact_ids,
                "error_message": sam3_summary.error_message,
                "detections": sam3_summary.detections,
            },
        }
