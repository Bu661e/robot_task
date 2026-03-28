from __future__ import annotations

import json
from typing import Any, Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse

from ..errors import ApiError
from ..schemas import ArtifactMetadata, ArtifactType
from ..services.artifact_store import ArtifactStore


router = APIRouter(tags=["artifacts"])


def get_artifact_store(request: Request) -> ArtifactStore:
    return request.app.state.artifact_store


def parse_ext_json(raw_ext: str | None) -> dict[str, Any]:
    if raw_ext is None or raw_ext == "":
        return {}
    try:
        parsed = json.loads(raw_ext)
    except json.JSONDecodeError as exc:
        raise ApiError(
            status_code=400,
            error_code="INVALID_REQUEST",
            message="Form field 'ext' must be valid JSON.",
        ) from exc
    if not isinstance(parsed, dict):
        raise ApiError(
            status_code=400,
            error_code="INVALID_REQUEST",
            message="Form field 'ext' must decode to a JSON object.",
        )
    return parsed


@router.post(
    "/artifacts",
    response_model=ArtifactMetadata,
    status_code=status.HTTP_201_CREATED,
)
async def upload_artifact(
    request: Request,
    artifact_type: Annotated[ArtifactType, Form()],
    file: Annotated[UploadFile, File()],
    ext: Annotated[str | None, Form()] = None,
    artifact_store: ArtifactStore = Depends(get_artifact_store),
) -> ArtifactMetadata:
    data = await file.read()
    metadata = artifact_store.save_bytes(
        artifact_type=artifact_type,
        filename=file.filename or "artifact.bin",
        content_type=file.content_type or "application/octet-stream",
        data=data,
        ext=parse_ext_json(ext),
    )
    return metadata


@router.get("/artifacts/{artifact_id}/content")
def download_artifact(
    artifact_id: str,
    artifact_store: ArtifactStore = Depends(get_artifact_store),
) -> FileResponse:
    metadata = artifact_store.get_metadata(artifact_id)
    content_path = artifact_store.get_content_path(artifact_id)
    return FileResponse(
        path=content_path,
        media_type=metadata.content_type,
        filename=metadata.filename,
    )
