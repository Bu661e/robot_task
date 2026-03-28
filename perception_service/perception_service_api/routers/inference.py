from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from perception_service_api.schemas import PerceptionRequest, PerceptionResponse
from perception_service_api.services.inference_service import PerceptionInferenceService


router = APIRouter(tags=["perception"])


def get_inference_service(request: Request) -> PerceptionInferenceService:
    return request.app.state.inference_service


@router.post("/perception/infer", response_model=PerceptionResponse)
def infer(
    payload: PerceptionRequest,
    inference_service: PerceptionInferenceService = Depends(get_inference_service),
) -> PerceptionResponse:
    return inference_service.infer(payload)
