from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class CameraIntrinsics(StrictModel):
    fx: float
    fy: float
    cx: float
    cy: float
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class CameraExtrinsics(StrictModel):
    translation: list[float] = Field(min_length=3, max_length=3)
    quaternion_wxyz: list[float] = Field(min_length=4, max_length=4)


class ObservationPayload(StrictModel):
    camera_id: str
    rgb_artifact_id: str
    depth_artifact_id: str
    depth_scale_m_per_unit: float | None = Field(default=None, gt=0)
    camera_intrinsics: CameraIntrinsics
    camera_extrinsics: CameraExtrinsics | None = None
    camera_frame_id: str
    timestamp: datetime


class ContextPayload(StrictModel):
    session_id: str | None = None
    environment_id: str | None = None
    camera_name: str | None = None


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
    observation: ObservationPayload
    context: ContextPayload
    options: OptionsPayload
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


class PerceptionResponse(StrictModel):
    request_id: str
    success: bool
    coordinate_frame: str
    timestamp: datetime
    detected_objects: list[DetectedObject]
    scene_artifacts: SceneArtifacts
    error: dict[str, Any] = Field(default_factory=dict)
    ext: dict[str, Any] = Field(default_factory=dict)
