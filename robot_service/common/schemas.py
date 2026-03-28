from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SessionStatus = Literal["starting", "ready", "stopped", "error"]
TaskStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskContent(BaseSchema):
    task_id: str
    instruction: str
    object_texts: list[str] = Field(default_factory=list)

    @field_validator("task_id", "instruction")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped


class CreateSessionRequest(BaseSchema):
    backend_type: str
    environment_id: str
    ext: dict[str, Any] = Field(default_factory=dict)

    @field_validator("backend_type", "environment_id")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped


class SessionResponse(BaseSchema):
    session_id: str
    backend_type: str
    environment_id: str
    session_status: SessionStatus
    ext: dict[str, Any] = Field(default_factory=dict)


class RobotStatusResponse(BaseSchema):
    session_id: str
    robot_status: Literal["ready", "busy", "error"]
    timestamp: str
    ext: dict[str, Any] = Field(default_factory=dict)


class ArtifactRef(BaseSchema):
    artifact_id: str
    content_type: str


class CameraIntrinsics(BaseSchema):
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int


class CameraExtrinsics(BaseSchema):
    translation: list[float]
    quaternion_wxyz: list[float]


class CameraPayload(BaseSchema):
    camera_id: str
    rgb_image: ArtifactRef
    depth_image: ArtifactRef
    intrinsics: CameraIntrinsics
    extrinsics: CameraExtrinsics
    ext: dict[str, Any] = Field(default_factory=dict)


class CamerasResponse(BaseSchema):
    session_id: str
    timestamp: str
    cameras: list[CameraPayload]
    ext: dict[str, Any] = Field(default_factory=dict)


class ActionApisResponse(BaseSchema):
    session_id: str
    action_apis: list[str]
    ext: dict[str, Any] = Field(default_factory=dict)


class CreateTaskRequest(BaseSchema):
    task: TaskContent
    policy_source: str
    perception_data: dict[str, Any]
    ext: dict[str, Any] = Field(default_factory=dict)

    @field_validator("policy_source")
    @classmethod
    def _strip_policy_source(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped


class TaskResponse(BaseSchema):
    session_id: str
    session_task_id: str
    task_status: TaskStatus
    task: TaskContent
    policy_source: str
    perception_data: dict[str, Any]
    created_at: str
    updated_at: str
    ext: dict[str, Any] = Field(default_factory=dict)


class TaskListResponse(BaseSchema):
    session_id: str
    tasks: list[TaskResponse]
    ext: dict[str, Any] = Field(default_factory=dict)


class ArtifactRecord(BaseSchema):
    artifact_id: str
    session_id: str
    content_type: str
    file_path: str
    ext: dict[str, Any] = Field(default_factory=dict)
