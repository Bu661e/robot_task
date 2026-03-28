from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from typing import Any

from perception_service_api.errors import ApiError
from perception_service_api.settings import (
    SAM3_BACKEND_SCRIPT,
    SAM3_PYTHON,
    SAM3D_OBJECTS_BACKEND_SCRIPT,
    SAM3D_OBJECTS_PYTHON,
)
from perception_service_api.schemas import (
    PerceptionRequest,
    PerceptionResponse,
    SceneArtifacts,
)
from perception_service_api.services.artifact_store import ArtifactStore
from perception_service_api.services.backend_runner import BackendCommand
from perception_service_api.services.pointmap import (
    depth_to_pointmap,
    load_depth_meters,
    load_rgb_size,
)


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

        rgb_metadata = self.artifact_store.get_metadata(request.observation.rgb_artifact_id)
        depth_metadata = self.artifact_store.get_metadata(request.observation.depth_artifact_id)

        self._assert_artifact_type(rgb_metadata.artifact_type, "rgb_image", rgb_metadata.artifact_id)
        self._assert_artifact_type(depth_metadata.artifact_type, "depth_image", depth_metadata.artifact_id)

        rgb_path = self.artifact_store.get_content_path(rgb_metadata.artifact_id)
        depth_path = self.artifact_store.get_content_path(depth_metadata.artifact_id)

        rgb_width, rgb_height = load_rgb_size(rgb_metadata, rgb_path)
        intrinsics = request.observation.camera_intrinsics
        if rgb_width != intrinsics.width or rgb_height != intrinsics.height:
            raise ApiError(
                status_code=400,
                error_code="INVALID_REQUEST",
                message="RGB resolution does not match camera intrinsics.",
                ext={
                    "details": {
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
            depth_scale_m_per_unit=request.observation.depth_scale_m_per_unit,
        )
        pointmap_result = depth_to_pointmap(depth_m, intrinsics)
        backend_status = self._collect_backend_status(request_id=request_id)

        debug_artifact_ids: list[str] = []
        if request.options.include_debug_artifacts:
            debug_payload = self._build_debug_payload(
                request_id=request_id,
                request=request,
                rgb_artifact_id=rgb_metadata.artifact_id,
                depth_artifact_id=depth_metadata.artifact_id,
                pointmap_result=pointmap_result,
                backend_status=backend_status,
            )
            debug_metadata = self.artifact_store.save_bytes(
                artifact_type="debug_json",
                filename=f"{request_id}_preflight.json",
                content_type="application/json",
                data=json.dumps(debug_payload, ensure_ascii=True, indent=2).encode("utf-8"),
                ext={},
            )
            debug_artifact_ids.append(debug_metadata.artifact_id)

        return PerceptionResponse(
            request_id=request_id,
            success=False,
            coordinate_frame="camera",
            timestamp=datetime.now(timezone.utc),
            detected_objects=[],
            scene_artifacts=SceneArtifacts(
                visualization_artifact_ids=[],
                debug_artifact_ids=debug_artifact_ids,
            ),
            error={
                "code": "INTERNAL_ERROR",
                "message": "Inference backends are not producing detections yet. Request validation and internal pointmap generation completed.",
            },
            ext={
                "matched_object_texts": [],
                "unmatched_object_texts": list(request.task.object_texts),
                "pointmap_generated": True,
                "backend_status": backend_status,
            },
        )

    @staticmethod
    def _assert_artifact_type(actual: str, expected: str, artifact_id: str) -> None:
        if actual != expected:
            raise ApiError(
                status_code=400,
                error_code="ARTIFACT_TYPE_MISMATCH",
                message="Artifact type does not match request field.",
                ext={"details": {"artifact_id": artifact_id, "expected": expected, "actual": actual}},
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
        rgb_artifact_id: str,
        depth_artifact_id: str,
        pointmap_result: Any,
        backend_status: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "request_id": request_id,
            "task_id": request.task.task_id,
            "object_texts": list(request.task.object_texts),
            "observation": {
                "camera_id": request.observation.camera_id,
                "camera_frame_id": request.observation.camera_frame_id,
                "rgb_artifact_id": rgb_artifact_id,
                "depth_artifact_id": depth_artifact_id,
                "depth_scale_m_per_unit": request.observation.depth_scale_m_per_unit,
            },
            "pointmap": {
                "width": pointmap_result.width,
                "height": pointmap_result.height,
                "valid_fraction": pointmap_result.valid_fraction,
                "min_depth_m": pointmap_result.min_depth_m,
                "max_depth_m": pointmap_result.max_depth_m,
            },
            "backends": backend_status,
        }
