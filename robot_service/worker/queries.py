from __future__ import annotations

from datetime import datetime, timezone

from robot_service.common.schemas import ActionApisResponse, ArtifactRecord, CamerasResponse, RobotStatusResponse
from robot_service.worker.environment import EnvironmentRuntime


def _utc_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_robot_status(session_id: str, runtime: EnvironmentRuntime) -> RobotStatusResponse:
    return RobotStatusResponse(
        session_id=session_id,
        robot_status=runtime.robot_status,  # type: ignore[arg-type]
        timestamp=_utc_iso(),
        ext={"environment_id": runtime.current_environment_id},
    )


def build_cameras_payload(session_id: str, runtime: EnvironmentRuntime) -> tuple[CamerasResponse, list[ArtifactRecord]]:
    cameras, artifact_records, ext = runtime.capture_camera_payloads(session_id)
    return CamerasResponse(
        session_id=session_id,
        timestamp=_utc_iso(),
        cameras=cameras,
        ext=ext,
    ), artifact_records


def build_action_apis_payload(session_id: str, runtime: EnvironmentRuntime) -> ActionApisResponse:
    return ActionApisResponse(
        session_id=session_id,
        action_apis=runtime.action_apis,
        ext={"environment_id": runtime.current_environment_id},
    )
