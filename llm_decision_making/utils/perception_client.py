from __future__ import annotations

import json
from typing import Mapping

import httpx

from config.perception_config import (
    PERCEPTION_BASE_URL,
    PERCEPTION_TIMEOUT_S,
    PERCEPTION_TRUST_ENV,
)
from utils.perception_schemas import ArtifactMetadata, PerceptionRequest, PerceptionResponse
from utils.run_logging import get_active_run_logger


class PerceptionClientError(RuntimeError):
    pass


_ARTIFACT_FILE_SUFFIXES: dict[str, str] = {
    "image/png": ".png",
    "application/x-npy": ".npy",
    "application/json": ".json",
    "text/plain": ".txt",
    "model/gltf-binary": ".glb",
    "application/ply": ".ply",
    "application/x-ply": ".ply",
}


def _artifact_filename(artifact_id: str, content_type: str | None) -> str:
    if content_type is None:
        return artifact_id

    normalized_content_type = content_type.split(";", 1)[0].strip().lower()
    suffix = _ARTIFACT_FILE_SUFFIXES.get(normalized_content_type)
    if suffix is None:
        return artifact_id

    return f"{artifact_id}{suffix}"


class PerceptionClient:
    def __init__(
        self,
        base_url: str,
        timeout_s: float,
        trust_env: bool,
    ) -> None:
        self._base_url = base_url
        self._timeout_s = timeout_s
        self._trust_env = trust_env
        self._client: httpx.Client | None = None

    def upload_artifact(
        self,
        filename: str,
        content: bytes,
        artifact_type: str,
        content_type: str,
        ext: Mapping[str, object] | None = None,
    ) -> ArtifactMetadata:
        ext_payload = dict(ext or {})
        response_payload = self._request_json(
            method="POST",
            url="/artifacts",
            data={
                "artifact_type": artifact_type,
                "ext": json.dumps(ext_payload),
            },
            files={
                "file": (filename, content, content_type),
            },
            log_body={
                "artifact_type": artifact_type,
                "filename": filename,
                "content_type": content_type,
                "size_bytes": len(content),
                "ext": ext_payload,
            },
        )
        return ArtifactMetadata.from_dict(response_payload)

    def infer(self, request: PerceptionRequest) -> PerceptionResponse:
        response_payload = self._request_json(
            method="POST",
            url="/perception/infer",
            json_body=request.to_dict(),
        )
        return PerceptionResponse.from_dict(response_payload)

    def download_artifact(
        self,
        artifact_id: str,
        content_type: str | None = None,
    ) -> bytes:
        url = f"/artifacts/{artifact_id}/content"
        run_logger = get_active_run_logger()
        service_logger = None
        request_id: str | None = None
        if run_logger is not None:
            service_logger = run_logger.service("perception_service")
            request_id = service_logger.log_http_request(
                method="GET",
                path=url,
                body=None,
            )

        response = self._get_client().request("GET", url)
        response_headers = getattr(response, "headers", {})
        response_content_type = None
        if hasattr(response_headers, "get"):
            raw_content_type = response_headers.get("content-type")
            if isinstance(raw_content_type, str):
                response_content_type = raw_content_type

        resolved_content_type = content_type or response_content_type
        filename = _artifact_filename(artifact_id, resolved_content_type)
        if service_logger is not None and request_id is not None:
            if response.status_code >= 400:
                response_payload: object
                try:
                    response_payload = response.json()
                except ValueError:
                    response_payload = {"message": "Binary artifact request failed."}
                service_logger.log_http_response(
                    request_id=request_id,
                    method="GET",
                    path=url,
                    status_code=response.status_code,
                    body=response_payload,
                )
            else:
                artifact_path = service_logger.save_binary_artifact(
                    filename=filename,
                    content=response.content,
                    log_event=False,
                )
                relative_path = artifact_path.relative_to(run_logger.root_dir)
                service_logger.log_http_response(
                    request_id=request_id,
                    method="GET",
                    path=url,
                    status_code=response.status_code,
                    body={
                        "artifact_path": str(relative_path),
                        "size_bytes": len(response.content),
                    },
                    summary=f"GET {url} path={relative_path} size_bytes={len(response.content)}",
                )

        self._raise_for_error_response(response)
        return response.content

    def _request_json(
        self,
        method: str,
        url: str,
        json_body: Mapping[str, object] | None = None,
        data: Mapping[str, object] | None = None,
        files: Mapping[str, object] | None = None,
        log_body: object | None = None,
    ) -> Mapping[str, object]:
        run_logger = get_active_run_logger()
        service_logger = None
        request_id: str | None = None
        if run_logger is not None:
            service_logger = run_logger.service("perception_service")
            request_id = service_logger.log_http_request(
                method=method,
                path=url,
                body=log_body if log_body is not None else json_body,
            )

        response = self._get_client().request(
            method,
            url,
            json=json_body,
            data=data,
            files=files,
        )
        if service_logger is not None and request_id is not None:
            response_payload: object
            try:
                response_payload = response.json()
            except ValueError:
                response_payload = {"message": "Response body is not valid JSON."}
            service_logger.log_http_response(
                request_id=request_id,
                method=method,
                path=url,
                status_code=response.status_code,
                body=response_payload,
            )

        self._raise_for_error_response(response)
        response_payload = response.json()
        if not isinstance(response_payload, Mapping):
            raise PerceptionClientError("Perception service response must be a JSON object.")

        return response_payload

    def _raise_for_error_response(self, response: object) -> None:
        status_code = getattr(response, "status_code")
        if not isinstance(status_code, int):
            raise PerceptionClientError("Perception service response is missing status code.")

        if status_code < 400:
            return

        try:
            response_payload = response.json()
        except ValueError:
            raise PerceptionClientError(
                f"Perception service request failed with status {status_code}."
            ) from None

        if isinstance(response_payload, Mapping):
            error_code = response_payload.get("error_code")
            message = response_payload.get("message")
            raise PerceptionClientError(
                f"Perception service request failed: {error_code} {message}"
            )

        raise PerceptionClientError(
            f"Perception service request failed with status {status_code}."
        )

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout_s,
                trust_env=self._trust_env,
            )

        return self._client


default_perception_client = PerceptionClient(
    base_url=PERCEPTION_BASE_URL,
    timeout_s=PERCEPTION_TIMEOUT_S,
    trust_env=PERCEPTION_TRUST_ENV,
)
