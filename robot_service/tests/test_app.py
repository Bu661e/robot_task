from __future__ import annotations

import threading

from fastapi.testclient import TestClient

from robot_service.api.app import create_app
from robot_service.api.manager import RobotServiceManager
from robot_service.common.messages import WorkerEvent
from robot_service.runtime.settings import Settings


class FakeWorkerHandle:
    def __init__(self) -> None:
        self.commands = []
        self._closed = False
        self._run_task_started = threading.Event()
        self._finish_run_task = threading.Event()

    def send(self, command, timeout_s: float) -> WorkerEvent:
        self.commands.append(command)
        if command.command_type == "load_environment":
            return WorkerEvent(
                request_id=command.request_id,
                event_type="environment_loaded",
                payload={"environment_id": command.payload["environment_id"]},
            )
        if command.command_type == "run_task":
            self._run_task_started.set()
            self._finish_run_task.wait(timeout=timeout_s)
            return WorkerEvent(
                request_id=command.request_id,
                event_type="task_succeeded",
                payload={},
            )
        if command.command_type == "shutdown":
            self._closed = True
            return WorkerEvent(request_id=command.request_id, event_type="worker_ready", payload={})
        if command.command_type == "get_robot_status":
            return WorkerEvent(
                request_id=command.request_id,
                event_type="robot_status",
                payload={"robot_status": "ready", "timestamp": "2026-03-28T00:00:00Z"},
            )
        raise AssertionError(f"Unexpected command type: {command.command_type}")

    def close(self) -> None:
        self._closed = True

    def is_alive(self) -> bool:
        return not self._closed

    def wait_for_task_start(self) -> None:
        assert self._run_task_started.wait(timeout=1.0)


def create_test_client() -> tuple[TestClient, FakeWorkerHandle]:
    handle = FakeWorkerHandle()
    manager = RobotServiceManager(
        settings=Settings(
            robot_service_host="127.0.0.1",
            robot_service_port=8000,
            isaac_sim_root="/opt/isaacsim",
            runs_dir="robot_service/runs",  # type: ignore[arg-type]
            log_level="INFO",
        ),
        worker_factory=lambda session_id, session_dir: handle,
    )
    return TestClient(create_app(manager)), handle


def test_post_sessions_returns_ready_session():
    client, _ = create_test_client()

    response = client.post(
        "/sessions",
        json={"backend_type": "isaac_sim", "environment_id": "env-default"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_status"] == "ready"
    assert payload["environment_id"] == "env-default"


def test_second_session_request_returns_409():
    client, _ = create_test_client()
    client.post("/sessions", json={"backend_type": "isaac_sim", "environment_id": "env-default"})

    response = client.post(
        "/sessions",
        json={"backend_type": "isaac_sim", "environment_id": "env-second"},
    )

    assert response.status_code == 409


def test_post_task_returns_queued_task():
    client, _ = create_test_client()
    session = client.post(
        "/sessions",
        json={"backend_type": "isaac_sim", "environment_id": "env-default"},
    ).json()

    response = client.post(
        f"/sessions/{session['session_id']}/tasks",
        json={
            "task": {
                "task_id": "task-1",
                "instruction": "Pick up the cube",
                "object_texts": ["cube"],
            },
            "policy_source": "def run_policy(robot, perception_data):\n    return None",
            "perception_data": {"objects": []},
        },
    )

    assert response.status_code == 200
    assert response.json()["task_status"] == "queued"


def test_delete_session_while_task_is_running_returns_409():
    client, handle = create_test_client()
    session = client.post(
        "/sessions",
        json={"backend_type": "isaac_sim", "environment_id": "env-default"},
    ).json()
    client.post(
        f"/sessions/{session['session_id']}/tasks",
        json={
            "task": {
                "task_id": "task-1",
                "instruction": "Pick up the cube",
                "object_texts": ["cube"],
            },
            "policy_source": "def run_policy(robot, perception_data):\n    return None",
            "perception_data": {"objects": []},
        },
    )

    handle.wait_for_task_start()
    response = client.delete(f"/sessions/{session['session_id']}")

    assert response.status_code == 409
