from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .errors import ApiError
from .routers.artifacts import router as artifacts_router
from .routers.health import router as health_router
from .routers.inference import router as inference_router
from .services.artifact_store import ArtifactStore
from .services.inference_service import PerceptionInferenceService
from .settings import ARTIFACTS_DIR


def create_app() -> FastAPI:
    app = FastAPI(title="perception_service", version="0.1.0")

    artifact_store = ArtifactStore(ARTIFACTS_DIR)
    app.state.artifact_store = artifact_store
    app.state.inference_service = PerceptionInferenceService(artifact_store)

    app.include_router(health_router)
    app.include_router(artifacts_router)
    app.include_router(inference_router)

    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": exc.error_code,
                "message": exc.message,
                "ext": exc.ext,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "INVALID_REQUEST",
                "message": "Request validation failed.",
                "ext": {"details": exc.errors()},
            },
        )

    return app


app = create_app()
