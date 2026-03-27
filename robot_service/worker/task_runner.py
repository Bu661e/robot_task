from __future__ import annotations

from robot_service.common.messages import WorkerEvent
from robot_service.common.schemas import CreateTaskRequest
from robot_service.worker.environment import EnvironmentRuntime


class TaskRunner:
    def __init__(self, runtime: EnvironmentRuntime) -> None:
        self._runtime = runtime
        self._current_session_task_id: str | None = None

    def run_task(
        self,
        session_id: str,
        session_task_id: str,
        request: CreateTaskRequest,
        request_id: str | None = None,
    ) -> WorkerEvent:
        if self._runtime.current_environment_id is None:
            return WorkerEvent(
                request_id=request_id or session_task_id,
                event_type="task_failed",
                payload={"error_message": "Environment is not loaded."},
            )

        self._current_session_task_id = session_task_id
        del request  # Real task execution will be added once Isaac Sim is available on the target host.
        self._current_session_task_id = None
        return WorkerEvent(
            request_id=request_id or session_task_id,
            event_type="task_succeeded",
            payload={"session_id": session_id, "session_task_id": session_task_id},
        )

    def cancel_current_task(self, request_id: str = "cancel-current-task") -> WorkerEvent:
        if self._current_session_task_id is None:
            return WorkerEvent(
                request_id=request_id,
                event_type="task_failed",
                payload={"error_message": "No running task to cancel."},
            )
        session_task_id = self._current_session_task_id
        self._current_session_task_id = None
        return WorkerEvent(
            request_id=request_id,
            event_type="task_cancelled",
            payload={"session_task_id": session_task_id},
        )

