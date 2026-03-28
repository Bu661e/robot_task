from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from robot_service.api.manager import RobotServiceError, RobotServiceManager
from robot_service.common.schemas import (
    CamerasResponse,
    CreateSessionRequest,
    RobotStatusResponse,
    SessionResponse,
)
from robot_service.runtime.settings import Settings


def create_app(manager: RobotServiceManager | None = None) -> FastAPI:
    app = FastAPI(title="robot_service")
    app.state.manager = manager or RobotServiceManager(settings=Settings.from_env())

    @app.exception_handler(RobotServiceError)
    async def handle_robot_service_error(_, exc: RobotServiceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.post("/sessions", response_model=SessionResponse)
    async def create_session(request: CreateSessionRequest) -> SessionResponse:
        return app.state.manager.create_session(request)

    @app.get("/sessions/{session_id}", response_model=SessionResponse)
    async def get_session(session_id: str) -> SessionResponse:
        return app.state.manager.get_session(session_id)

    @app.delete("/sessions/{session_id}", response_model=SessionResponse)
    async def delete_session(session_id: str) -> SessionResponse:
        return app.state.manager.delete_session(session_id)

    @app.get("/sessions/{session_id}/robot", response_model=RobotStatusResponse)
    async def get_robot_status(session_id: str) -> RobotStatusResponse:
        return app.state.manager.get_robot_status(session_id)

    @app.get("/sessions/{session_id}/cameras", response_model=CamerasResponse)
    async def get_cameras(session_id: str) -> CamerasResponse:
        return app.state.manager.get_cameras(session_id)

    @app.get("/artifacts/{artifact_id}")
    async def download_artifact(artifact_id: str) -> FileResponse:
        artifact = app.state.manager.get_artifact(artifact_id)
        return FileResponse(path=artifact.file_path, media_type=artifact.content_type, filename=artifact.artifact_id)

    return app
