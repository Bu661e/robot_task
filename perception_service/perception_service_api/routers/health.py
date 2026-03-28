from __future__ import annotations

from fastapi import APIRouter

from perception_service_api.schemas import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(service="perception_service", status="ok", ext={})
