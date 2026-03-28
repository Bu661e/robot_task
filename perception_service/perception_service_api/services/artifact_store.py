from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from perception_service_api.errors import ApiError
from perception_service_api.schemas import ArtifactMetadata, ArtifactType


class ArtifactStore:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def save_bytes(
        self,
        *,
        artifact_type: ArtifactType,
        filename: str,
        content_type: str,
        data: bytes,
        ext: dict[str, Any] | None = None,
    ) -> ArtifactMetadata:
        created_at = datetime.now(timezone.utc)
        artifact_id = self._build_artifact_id(artifact_type, created_at)
        artifact_dir = self.root_dir / artifact_id
        artifact_dir.mkdir(parents=True, exist_ok=False)

        content_path = artifact_dir / "content"
        metadata_path = artifact_dir / "metadata.json"
        content_path.write_bytes(data)

        metadata = ArtifactMetadata(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            content_type=content_type or "application/octet-stream",
            filename=filename or "artifact.bin",
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            created_at=created_at,
            ext=ext or {},
        )
        metadata_path.write_text(
            json.dumps(metadata.model_dump(mode="json"), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        return metadata

    def get_metadata(self, artifact_id: str) -> ArtifactMetadata:
        metadata_path = self.root_dir / artifact_id / "metadata.json"
        if not metadata_path.is_file():
            raise ApiError(
                status_code=404,
                error_code="ARTIFACT_NOT_FOUND",
                message="Requested artifact not found.",
                ext={"details": {"artifact_id": artifact_id}},
            )
        return ArtifactMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))

    def get_content_path(self, artifact_id: str) -> Path:
        content_path = self.root_dir / artifact_id / "content"
        if not content_path.is_file():
            raise ApiError(
                status_code=404,
                error_code="ARTIFACT_NOT_FOUND",
                message="Requested artifact not found.",
                ext={"details": {"artifact_id": artifact_id}},
            )
        return content_path

    @staticmethod
    def _build_artifact_id(artifact_type: ArtifactType, created_at: datetime) -> str:
        stamp = created_at.strftime("%Y%m%d%H%M%S")
        suffix = secrets.token_hex(4)
        return f"artifact_{artifact_type}_{stamp}_{suffix}"
