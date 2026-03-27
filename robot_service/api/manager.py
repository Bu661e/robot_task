from __future__ import annotations

import json
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from secrets import token_hex
from typing import Protocol

from robot_service.common.messages import WorkerCommand, WorkerEvent
from robot_service.common.schemas import (
    ActionApisResponse,
    ArtifactRecord,
    CamerasResponse,
    CreateSessionRequest,
    CreateTaskRequest,
    RobotStatusResponse,
    SessionResponse,
    TaskListResponse,
    TaskResponse,
)
from robot_service.runtime.ids import new_session_id, new_session_task_id
from robot_service.runtime.paths import get_runs_dir, get_session_run_dir
from robot_service.runtime.settings import Settings


class RobotServiceError(Exception):
    status_code = 500

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class RobotServiceConflictError(RobotServiceError):
    status_code = 409


class RobotServiceNotFoundError(RobotServiceError):
    status_code = 404


class RobotServiceValidationError(RobotServiceError):
    status_code = 400


class WorkerHandleProtocol(Protocol):
    def send(self, command: WorkerCommand, timeout_s: float) -> WorkerEvent: ...

    def close(self) -> None: ...

    def is_alive(self) -> bool: ...


def _utc_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class SubprocessWorkerHandle:
    def __init__(self, settings: Settings, session_id: str, session_dir: Path) -> None:
        if not settings.isaac_sim_root:
            raise RobotServiceValidationError("ISAAC_SIM_ROOT is required to start the worker.")

        self._session_id = session_id
        self._session_dir = session_dir
        self._lock = threading.Lock()
        worker_entrypoint = Path(__file__).resolve().parent.parent / "worker" / "entrypoint.py"
        python_sh = Path(settings.isaac_sim_root) / "python.sh"

        self._process = subprocess.Popen(
            [
                str(python_sh),
                str(worker_entrypoint),
                "--session-id",
                session_id,
                "--session-dir",
                str(session_dir),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def send(self, command: WorkerCommand, timeout_s: float) -> WorkerEvent:
        del timeout_s  # Timeout handling is deferred until the worker integration is available.
        if self._process.stdin is None or self._process.stdout is None:
            raise RobotServiceError("Worker pipes are unavailable.")

        with self._lock:
            self._process.stdin.write(command.model_dump_json() + "\n")
            self._process.stdin.flush()
            line = self._process.stdout.readline()

        if not line:
            raise RobotServiceError("Worker closed stdout before replying.")
        return WorkerEvent.model_validate(json.loads(line))

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)

    def is_alive(self) -> bool:
        return self._process.poll() is None


class RobotServiceManager:
    def __init__(
        self,
        settings: Settings,
        worker_factory=None,
    ) -> None:
        self._settings = settings
        self._worker_factory = worker_factory or self._build_worker
        self._lock = threading.RLock()
        self.active_session: SessionResponse | None = None
        self.current_task_id: str | None = None
        self.tasks_by_id: dict[str, TaskResponse] = {}
        self.worker_handle: WorkerHandleProtocol | None = None
        self.worker_thread: threading.Thread | None = None
        self.artifact_index: dict[str, ArtifactRecord] = {}

    def create_session(self, request: CreateSessionRequest) -> SessionResponse:
        with self._lock:
            if request.backend_type != "isaac_sim":
                raise RobotServiceValidationError("Only backend_type='isaac_sim' is currently supported.")
            if self.active_session is not None:
                raise RobotServiceConflictError("An active session already exists.")

            session_id = new_session_id(request.backend_type)
            runs_dir = get_runs_dir(self._settings.runs_dir)
            session_dir = get_session_run_dir(runs_dir, session_id)
            (session_dir / "artifacts").mkdir(parents=True, exist_ok=True)

            self.active_session = SessionResponse(
                session_id=session_id,
                backend_type=request.backend_type,
                environment_id=request.environment_id,
                session_status="starting",
                ext=request.ext,
            )

            try:
                self.worker_handle = self._worker_factory(session_id, session_dir)
                event = self._send_worker_command(
                    "load_environment",
                    {"environment_id": request.environment_id},
                )
            except Exception as exc:
                self._mark_session_error(str(exc))
                raise

            if event.event_type != "environment_loaded":
                self._mark_session_error(f"Unexpected worker event: {event.event_type}")
                raise RobotServiceError(f"Unexpected worker event: {event.event_type}")

            self.active_session = self.active_session.model_copy(
                update={"session_status": "ready", "environment_id": request.environment_id}
            )
            return self.active_session.model_copy(deep=True)

    def get_session(self, session_id: str) -> SessionResponse:
        with self._lock:
            session = self._require_active_session(session_id)
            return session.model_copy(deep=True)

    def delete_session(self, session_id: str) -> SessionResponse:
        with self._lock:
            session = self._require_active_session(session_id)
            if self.current_task_id is not None:
                task = self.tasks_by_id[self.current_task_id]
                if task.task_status in {"queued", "running"}:
                    raise RobotServiceConflictError("Cannot delete the session while a task is running.")

            if self.worker_handle is not None:
                try:
                    self._send_worker_command("shutdown", {})
                except RobotServiceError:
                    pass
                self.worker_handle.close()

            stopped = session.model_copy(update={"session_status": "stopped"})
            self.active_session = None
            self.current_task_id = None
            self.tasks_by_id.clear()
            self.worker_handle = None
            self.worker_thread = None
            self.artifact_index.clear()
            return stopped

    def get_robot_status(self, session_id: str) -> RobotStatusResponse:
        with self._lock:
            self._ensure_session_ready(session_id)
            event = self._send_worker_command("get_robot_status", {})
            if event.event_type != "robot_status":
                raise RobotServiceError(f"Unexpected worker event: {event.event_type}")
            return RobotStatusResponse(
                session_id=session_id,
                robot_status=event.payload["robot_status"],
                timestamp=event.payload["timestamp"],
                ext=event.payload.get("ext", {}),
            )

    def get_cameras(self, session_id: str) -> CamerasResponse:
        with self._lock:
            self._ensure_session_ready(session_id)
            event = self._send_worker_command("get_cameras", {})
            if event.event_type != "cameras_payload":
                raise RobotServiceError(f"Unexpected worker event: {event.event_type}")
            return CamerasResponse.model_validate(
                {
                    "session_id": session_id,
                    **event.payload,
                }
            )

    def get_action_apis(self, session_id: str) -> ActionApisResponse:
        with self._lock:
            self._ensure_session_ready(session_id)
            event = self._send_worker_command("get_action_apis", {})
            if event.event_type != "action_apis_payload":
                raise RobotServiceError(f"Unexpected worker event: {event.event_type}")
            return ActionApisResponse.model_validate(
                {
                    "session_id": session_id,
                    **event.payload,
                }
            )

    def create_task(self, session_id: str, request: CreateTaskRequest) -> TaskResponse:
        with self._lock:
            session = self._ensure_session_ready(session_id)
            self._ensure_no_active_task()

            now = _utc_iso()
            session_task_id = new_session_task_id()
            task_response = TaskResponse(
                session_id=session.session_id,
                session_task_id=session_task_id,
                task_status="queued",
                task=request.task,
                policy_source=request.policy_source,
                perception_data=request.perception_data,
                created_at=now,
                updated_at=now,
                ext=request.ext,
            )
            self.tasks_by_id[session_task_id] = task_response
            self.current_task_id = session_task_id

            self.worker_thread = threading.Thread(
                target=self._run_task_in_background,
                args=(session.session_id, session_task_id, request),
                daemon=True,
            )
            self.worker_thread.start()
            return task_response.model_copy(deep=True)

    def list_tasks(self, session_id: str) -> TaskListResponse:
        with self._lock:
            session = self._require_active_session(session_id)
            return TaskListResponse(
                session_id=session.session_id,
                tasks=[task.model_copy(deep=True) for task in self.tasks_by_id.values()],
                ext={},
            )

    def get_task(self, session_id: str, session_task_id: str) -> TaskResponse:
        with self._lock:
            self._require_active_session(session_id)
            task = self.tasks_by_id.get(session_task_id)
            if task is None:
                raise RobotServiceNotFoundError(f"Unknown task: {session_task_id}")
            return task.model_copy(deep=True)

    def cancel_task(self, session_id: str, session_task_id: str) -> TaskResponse:
        with self._lock:
            self._require_active_session(session_id)
            task = self.tasks_by_id.get(session_task_id)
            if task is None:
                raise RobotServiceNotFoundError(f"Unknown task: {session_task_id}")
            if task.task_status == "queued":
                cancelled = task.model_copy(update={"task_status": "cancelled", "updated_at": _utc_iso()})
                self.tasks_by_id[session_task_id] = cancelled
                self.current_task_id = None
                return cancelled.model_copy(deep=True)
            if task.task_status == "running":
                raise RobotServiceConflictError("Cancelling a running task is not supported yet.")
            return task.model_copy(deep=True)

    def get_artifact(self, artifact_id: str) -> ArtifactRecord:
        with self._lock:
            artifact = self.artifact_index.get(artifact_id)
            if artifact is None:
                raise RobotServiceNotFoundError(f"Unknown artifact: {artifact_id}")
            return artifact.model_copy(deep=True)

    def _build_worker(self, session_id: str, session_dir: Path) -> WorkerHandleProtocol:
        return SubprocessWorkerHandle(self._settings, session_id, session_dir)

    def _send_worker_command(self, command_type: str, payload: dict) -> WorkerEvent:
        if self.worker_handle is None:
            raise RobotServiceError("Worker is not available.")
        if not self.worker_handle.is_alive():
            raise RobotServiceError("Worker process is not alive.")
        command = WorkerCommand(
            request_id=f"req_{token_hex(4)}",
            command_type=command_type,  # type: ignore[arg-type]
            payload=payload,
        )
        return self.worker_handle.send(command, timeout_s=self._settings.worker_command_timeout_s)

    def _run_task_in_background(
        self,
        session_id: str,
        session_task_id: str,
        request: CreateTaskRequest,
    ) -> None:
        with self._lock:
            task = self.tasks_by_id[session_task_id]
            self.tasks_by_id[session_task_id] = task.model_copy(
                update={"task_status": "running", "updated_at": _utc_iso()}
            )

        try:
            event = self._send_worker_command(
                "run_task",
                {
                    "session_id": session_id,
                    "session_task_id": session_task_id,
                    "task": request.task.model_dump(mode="json"),
                    "policy_source": request.policy_source,
                    "perception_data": request.perception_data,
                    "ext": request.ext,
                },
            )
            final_status = {
                "task_succeeded": "succeeded",
                "task_failed": "failed",
                "task_cancelled": "cancelled",
            }.get(event.event_type)
            if final_status is None:
                raise RobotServiceError(f"Unexpected worker event: {event.event_type}")
            with self._lock:
                task = self.tasks_by_id[session_task_id]
                self.tasks_by_id[session_task_id] = task.model_copy(
                    update={"task_status": final_status, "updated_at": _utc_iso()}
                )
                self.current_task_id = None
        except Exception as exc:
            with self._lock:
                task = self.tasks_by_id[session_task_id]
                self.tasks_by_id[session_task_id] = task.model_copy(
                    update={
                        "task_status": "failed",
                        "updated_at": _utc_iso(),
                        "ext": {**task.ext, "error_message": str(exc)},
                    }
                )
                self.current_task_id = None
                self._mark_session_error(str(exc))

    def _require_active_session(self, session_id: str) -> SessionResponse:
        if self.active_session is None or self.active_session.session_id != session_id:
            raise RobotServiceNotFoundError(f"Unknown session: {session_id}")
        return self.active_session

    def _ensure_session_ready(self, session_id: str) -> SessionResponse:
        session = self._require_active_session(session_id)
        if session.session_status != "ready":
            raise RobotServiceConflictError("Session is not ready.")
        return session

    def _ensure_no_active_task(self) -> None:
        if self.current_task_id is None:
            return
        task = self.tasks_by_id[self.current_task_id]
        if task.task_status in {"queued", "running"}:
            raise RobotServiceConflictError("Another task is already active.")

    def _mark_session_error(self, reason: str) -> None:
        if self.active_session is None:
            return
        self.active_session = self.active_session.model_copy(
            update={"session_status": "error", "ext": {**self.active_session.ext, "error_message": reason}}
        )
