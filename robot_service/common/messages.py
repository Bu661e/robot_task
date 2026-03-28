from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


WorkerCommandType = Literal[
    "load_environment",
    "get_robot_status",
    "get_cameras",
    "get_action_apis",
    "run_task",
    "cancel_task",
    "shutdown",
]

WorkerEventType = Literal[
    "worker_ready",
    "environment_loaded",
    "robot_status",
    "cameras_payload",
    "action_apis_payload",
    "task_started",
    "task_succeeded",
    "task_failed",
    "task_cancelled",
    "artifact_created",
    "worker_error",
]


class BaseMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkerCommand(BaseMessage):
    request_id: str
    command_type: WorkerCommandType
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkerEvent(BaseMessage):
    request_id: str
    event_type: WorkerEventType
    payload: dict[str, Any] = Field(default_factory=dict)
