from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ArtifactType = Literal[
    "rgb_image",
    "depth_image",
    "mask_image",
    "mesh_glb",
    "gaussian_ply",
    "pointcloud_ply",
    "visualization_image",
    "debug_json",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictModel):
    service: str
    status: str
    ext: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(StrictModel):
    error_code: str
    message: str
    ext: dict[str, Any] = Field(default_factory=dict)


class ArtifactMetadata(StrictModel):
    artifact_id: str
    artifact_type: ArtifactType
    content_type: str
    filename: str
    size_bytes: int
    sha256: str
    created_at: datetime
    ext: dict[str, Any] = Field(default_factory=dict)


class TaskPayload(StrictModel):
    task_id: str
    instruction: str
    object_texts: list[str] = Field(min_length=1)


class ArtifactRef(StrictModel):
    artifact_id: str
    content_type: str | None = None


class Intrinsics(StrictModel):
    fx: float
    fy: float
    cx: float
    cy: float
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class Extrinsics(StrictModel):
    translation: list[float] = Field(min_length=3, max_length=3)
    quaternion_wxyz: list[float] = Field(min_length=4, max_length=4)


class ObservationPayload(StrictModel):
    camera_id: str
    rgb_image: ArtifactRef
    depth_image: ArtifactRef
    intrinsics: Intrinsics
    extrinsics: Extrinsics | None = None
    timestamp: datetime
    ext: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_shape(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)

        rgb_artifact_id = normalized.pop("rgb_artifact_id", None)
        if rgb_artifact_id is not None and "rgb_image" not in normalized:
            normalized["rgb_image"] = {"artifact_id": rgb_artifact_id}

        depth_artifact_id = normalized.pop("depth_artifact_id", None)
        if depth_artifact_id is not None and "depth_image" not in normalized:
            normalized["depth_image"] = {"artifact_id": depth_artifact_id}

        if "camera_intrinsics" in normalized and "intrinsics" not in normalized:
            normalized["intrinsics"] = normalized.pop("camera_intrinsics")

        if "camera_extrinsics" in normalized and "extrinsics" not in normalized:
            normalized["extrinsics"] = normalized.pop("camera_extrinsics")

        ext_payload = normalized.get("ext")
        if ext_payload is None:
            ext_payload = {}
        elif isinstance(ext_payload, dict):
            ext_payload = dict(ext_payload)
        else:
            return normalized

        for legacy_key in (
            "depth_scale_m_per_unit",
            "camera_frame_id",
            "depth_unit",
            "depth_encoding",
            "view_mode",
        ):
            if legacy_key in normalized and legacy_key not in ext_payload:
                ext_payload[legacy_key] = normalized.pop(legacy_key)

        normalized["ext"] = ext_payload
        return normalized

    @model_validator(mode="after")
    def validate_ext_fields(self) -> ObservationPayload:
        depth_scale = self.ext.get("depth_scale_m_per_unit")
        if depth_scale is not None:
            try:
                depth_scale_value = float(depth_scale)
            except (TypeError, ValueError) as exc:
                raise ValueError("observations[].ext.depth_scale_m_per_unit must be a positive number.") from exc
            if depth_scale_value <= 0:
                raise ValueError("observations[].ext.depth_scale_m_per_unit must be a positive number.")

        for key in ("camera_frame_id", "depth_unit", "depth_encoding", "view_mode"):
            value = self.ext.get(key)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"observations[].ext.{key} must be a string.")

        return self

    @property
    def depth_scale_m_per_unit(self) -> float | None:
        value = self.ext.get("depth_scale_m_per_unit")
        if value is None:
            return None
        return float(value)

    @property
    def camera_frame_id(self) -> str | None:
        value = self.ext.get("camera_frame_id")
        if value is None:
            return None
        return str(value)


class ContextPayload(StrictModel):
    session_id: str | None = None
    environment_id: str | None = None


class OptionsPayload(StrictModel):
    include_mask_artifacts: bool
    include_visualization_artifacts: bool
    include_debug_artifacts: bool
    include_mesh_glb_artifacts: bool
    include_gaussian_ply_artifacts: bool
    include_pointcloud_artifacts: bool
    max_objects_per_label: int = Field(gt=0)


class PerceptionRequest(StrictModel):
    task: TaskPayload
    observations: list[ObservationPayload] = Field(min_length=1)
    context: ContextPayload
    options: OptionsPayload
    ext: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_observation_field(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        if "observation" in normalized and "observations" not in normalized:
            normalized["observations"] = [normalized.pop("observation")]
        return normalized


class Sam3DetectionPayload(StrictModel):
    label: str
    source_object_text: str
    score: float
    bbox_2d_xyxy: list[int] = Field(min_length=4, max_length=4)
    mask_png_base64: str | None = None
    ext: dict[str, Any] = Field(default_factory=dict)


class Sam3BackendPayload(StrictModel):
    backend: str
    status: str
    detections: list[Sam3DetectionPayload] = Field(default_factory=list)
    error_message: str | None = None
    ext: dict[str, Any] = Field(default_factory=dict)


class SceneArtifacts(StrictModel):
    visualization_artifact_ids: list[str] = Field(default_factory=list)
    debug_artifact_ids: list[str] = Field(default_factory=list)


class DetectedObject(StrictModel):
    instance_id: str
    label: str
    source_object_text: str
    score: float
    source_mask_artifact_id: str | None
    bbox_2d_xyxy: list[int] = Field(min_length=4, max_length=4)
    translation_m: list[float] = Field(min_length=3, max_length=3)
    quaternion_wxyz: list[float] = Field(min_length=4, max_length=4)
    scale_m: list[float] = Field(min_length=3, max_length=3)
    mesh_glb_artifact_id: str | None = None
    gaussian_ply_artifact_id: str | None = None
    pointcloud_artifact_id: str | None = None
    ext: dict[str, Any] = Field(default_factory=dict)


class ObservationResult(StrictModel):
    camera_id: str
    observation_timestamp: datetime
    success: bool
    coordinate_frame: str
    detected_objects: list[DetectedObject]
    scene_artifacts: SceneArtifacts
    error: dict[str, Any] = Field(default_factory=dict)
    ext: dict[str, Any] = Field(default_factory=dict)


class PerceptionResponse(StrictModel):
    request_id: str
    success: bool
    timestamp: datetime
    observation_results: list[ObservationResult]
    error: dict[str, Any] = Field(default_factory=dict)
    ext: dict[str, Any] = Field(default_factory=dict)
