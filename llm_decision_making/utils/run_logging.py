from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from config.run_logging_config import RUNS_DIR


@dataclass(slots=True)
class ServicePaths:
    root_dir: Path
    requests_dir: Path
    responses_dir: Path
    artifacts_dir: Path


class _DualMessageFormatter(logging.Formatter):
    def __init__(self, mode: str) -> None:
        super().__init__(
            fmt="%(asctime)s | %(levelname)-5s | %(module_name)s | %(event_name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self._mode = mode

    def format(self, record: logging.LogRecord) -> str:
        message_attr = "console_message" if self._mode == "console" else "file_message"
        original_msg = record.msg
        original_args = record.args
        record.msg = getattr(record, message_attr, record.getMessage())
        record.args = ()

        try:
            return super().format(record)
        finally:
            record.msg = original_msg
            record.args = original_args


def _json_default(value: object) -> object:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable.")


def _render_json(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=_json_default,
    )


def _sanitize_path(path: str) -> str:
    normalized = path.strip("/")
    if not normalized:
        return "root"

    return normalized.replace("/", "_")


class ServiceRunLogger:
    def __init__(self, run_logger: RunLogger, service_name: str, paths: ServicePaths) -> None:
        self._run_logger = run_logger
        self._service_name = service_name
        self._paths = paths
        self._request_sequence = 0

    def log_http_request(
        self,
        method: str,
        path: str,
        body: object,
    ) -> str:
        self._request_sequence += 1
        request_id = f"{self._request_sequence:04d}"
        envelope = {
            "request_id": request_id,
            "service": self._service_name,
            "method": method,
            "path": path,
            "body": body,
        }
        request_file = self._paths.requests_dir / f"{request_id}_{method}_{_sanitize_path(path)}.json"
        request_file.write_text(_render_json(envelope), encoding="utf-8")
        self._run_logger._log(
            module=self._service_name,
            event="http_request",
            console_message=f"{method} {path}",
            file_message=_render_json(envelope),
        )
        return request_id

    def log_http_response(
        self,
        request_id: str,
        method: str,
        path: str,
        status_code: int,
        body: object,
        summary: str | None = None,
    ) -> None:
        envelope = {
            "request_id": request_id,
            "service": self._service_name,
            "method": method,
            "path": path,
            "status_code": status_code,
            "body": body,
        }
        response_file = self._paths.responses_dir / f"{request_id}_{method}_{_sanitize_path(path)}.json"
        response_file.write_text(_render_json(envelope), encoding="utf-8")
        self._run_logger._log(
            module=self._service_name,
            event="http_response",
            console_message=summary or f"{method} {path} status={status_code}",
            file_message=_render_json(envelope),
        )

    def save_binary_artifact(
        self,
        filename: str,
        content: bytes,
        log_event: bool = True,
    ) -> Path:
        artifact_path = self._paths.artifacts_dir / filename
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(content)
        if log_event:
            relative_path = artifact_path.relative_to(self._run_logger.root_dir)
            summary = f"path={relative_path} size_bytes={len(content)}"
            self._run_logger._log(
                module=self._service_name,
                event="artifact_saved",
                console_message=summary,
                file_message=summary,
            )
        return artifact_path


class RunLogger:
    def __init__(
        self,
        root_dir: Path,
        run_log_path: Path,
        logger: logging.Logger,
        services: dict[str, ServiceRunLogger],
    ) -> None:
        self.root_dir = root_dir
        self.run_log_path = run_log_path
        self._logger = logger
        self._services = services

    def service(self, service_name: str) -> ServiceRunLogger:
        return self._services[service_name]

    def log_data_flow(
        self,
        module: str,
        event: str,
        payload: object,
        summary: str,
    ) -> None:
        self._log(
            module=module,
            event=event,
            console_message=summary,
            file_message=_render_json(payload),
        )

    def _log(
        self,
        module: str,
        event: str,
        console_message: str,
        file_message: str,
        level: int = logging.INFO,
    ) -> None:
        self._logger.log(
            level,
            "",
            extra={
                "module_name": module,
                "event_name": event,
                "console_message": console_message,
                "file_message": file_message,
            },
        )

    def close(self) -> None:
        for handler in list(self._logger.handlers):
            handler.close()
            self._logger.removeHandler(handler)


_ACTIVE_RUN_LOGGER: RunLogger | None = None


def _build_service_paths(root_dir: Path, service_name: str) -> ServicePaths:
    service_root_dir = root_dir / service_name
    requests_dir = service_root_dir / "requests"
    responses_dir = service_root_dir / "responses"
    artifacts_dir = service_root_dir / "artifacts"
    requests_dir.mkdir(parents=True, exist_ok=True)
    responses_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return ServicePaths(
        root_dir=service_root_dir,
        requests_dir=requests_dir,
        responses_dir=responses_dir,
        artifacts_dir=artifacts_dir,
    )


def start_run_logging(
    task_id: str,
    base_dir: Path | None = None,
    started_at: datetime | None = None,
) -> RunLogger:
    global _ACTIVE_RUN_LOGGER

    if _ACTIVE_RUN_LOGGER is not None:
        _ACTIVE_RUN_LOGGER.close()
        _ACTIVE_RUN_LOGGER = None

    base_path = base_dir or RUNS_DIR
    timestamp = (started_at or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
    root_dir = base_path / f"{timestamp}_task-{task_id}"
    root_dir.mkdir(parents=True, exist_ok=True)
    run_log_path = root_dir / "run.log"
    run_log_path.touch()

    logger = logging.getLogger(f"llm_decision_making.run.{timestamp}.task-{task_id}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(_DualMessageFormatter(mode="console"))
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(run_log_path, encoding="utf-8")
    file_handler.setFormatter(_DualMessageFormatter(mode="file"))
    logger.addHandler(file_handler)

    services: dict[str, ServiceRunLogger] = {}
    for service_name in ("robot_service", "perception_service"):
        services[service_name] = ServiceRunLogger(
            run_logger=None,  # type: ignore[arg-type]
            service_name=service_name,
            paths=_build_service_paths(root_dir, service_name),
        )

    run_logger = RunLogger(
        root_dir=root_dir,
        run_log_path=run_log_path,
        logger=logger,
        services=services,
    )
    for service_logger in services.values():
        service_logger._run_logger = run_logger

    _ACTIVE_RUN_LOGGER = run_logger
    return run_logger


def get_active_run_logger() -> RunLogger | None:
    return _ACTIVE_RUN_LOGGER


def clear_active_run_logger() -> None:
    global _ACTIVE_RUN_LOGGER
    if _ACTIVE_RUN_LOGGER is not None:
        _ACTIVE_RUN_LOGGER.close()
        _ACTIVE_RUN_LOGGER = None
