from __future__ import annotations

import os
import pty
import threading
import time

import pytest

from robot_service.common.messages import WorkerCommand, WorkerEvent
from robot_service.common.schemas import CreateSessionRequest, CreateTaskRequest, TaskContent
from robot_service.runtime.settings import Settings
from robot_service.api.manager import (
    RobotServiceConflictError,
    RobotServiceManager,
    SubprocessWorkerHandle,
)


class FakeWorkerHandle:
    def __init__(self) -> None:
        self.commands = []
        self.timeouts = []
        self._closed = False
        self._run_task_started = threading.Event()
        self._finish_run_task = threading.Event()
        self._run_task_result = "task_succeeded"

    def send(self, command, timeout_s: float) -> WorkerEvent:
        self.commands.append(command)
        self.timeouts.append(timeout_s)
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
                event_type=self._run_task_result,
                payload={},
            )
        if command.command_type == "get_robot_status":
            return WorkerEvent(
                request_id=command.request_id,
                event_type="robot_status",
                payload={"robot_status": "ready", "timestamp": "2026-03-28T00:00:00Z"},
            )
        if command.command_type == "get_cameras":
            return WorkerEvent(
                request_id=command.request_id,
                event_type="cameras_payload",
                payload={
                    "timestamp": "2026-03-28T00:00:01Z",
                    "cameras": [
                        {
                            "camera_id": "table_top",
                            "rgb_image": {
                                "artifact_id": "artifact-rgb",
                                "content_type": "image/png",
                            },
                            "depth_image": {
                                "artifact_id": "artifact-depth",
                                "content_type": "application/x-npy",
                            },
                            "intrinsics": {
                                "fx": 500.0,
                                "fy": 500.0,
                                "cx": 320.0,
                                "cy": 320.0,
                                "width": 640,
                                "height": 640,
                            },
                            "extrinsics": {
                                "translation": [0.0, 0.0, 6.0],
                                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
                            },
                            "ext": {"depth_encoding": "npy-float32"},
                        },
                        {
                            "camera_id": "table_overview",
                            "rgb_image": {
                                "artifact_id": "artifact-rgb-overview",
                                "content_type": "image/png",
                            },
                            "depth_image": {
                                "artifact_id": "artifact-depth-overview",
                                "content_type": "application/x-npy",
                            },
                            "intrinsics": {
                                "fx": 505.0,
                                "fy": 505.0,
                                "cx": 320.0,
                                "cy": 320.0,
                                "width": 640,
                                "height": 640,
                            },
                            "extrinsics": {
                                "translation": [0.0, 1.8, 2.5],
                                "quaternion_xyzw": [0.0, 0.5, -0.8660254, 0.0],
                            },
                            "ext": {"depth_encoding": "npy-float32"},
                        }
                    ],
                    "artifact_records": [
                        {
                            "artifact_id": "artifact-rgb",
                            "session_id": "sess-demo",
                            "content_type": "image/png",
                            "file_path": "/tmp/artifact-rgb.png",
                            "ext": {},
                        },
                        {
                            "artifact_id": "artifact-depth",
                            "session_id": "sess-demo",
                            "content_type": "application/x-npy",
                            "file_path": "/tmp/artifact-depth.npy",
                            "ext": {},
                        },
                        {
                            "artifact_id": "artifact-rgb-overview",
                            "session_id": "sess-demo",
                            "content_type": "image/png",
                            "file_path": "/tmp/artifact-rgb-overview.png",
                            "ext": {},
                        },
                        {
                            "artifact_id": "artifact-depth-overview",
                            "session_id": "sess-demo",
                            "content_type": "application/x-npy",
                            "file_path": "/tmp/artifact-depth-overview.npy",
                            "ext": {},
                        },
                    ],
                    "ext": {"environment_id": "env-default"},
                },
            )
        if command.command_type == "shutdown":
            self._closed = True
            return WorkerEvent(
                request_id=command.request_id,
                event_type="worker_ready",
                payload={},
            )
        raise AssertionError(f"Unexpected command: {command.command_type}")

    def close(self) -> None:
        self._closed = True

    def is_alive(self) -> bool:
        return not self._closed

    def finish_task(self, result: str = "task_succeeded") -> None:
        self._run_task_result = result
        self._finish_run_task.set()

    def wait_for_task_start(self) -> None:
        assert self._run_task_started.wait(timeout=1.0)


def build_manager(handle: FakeWorkerHandle) -> RobotServiceManager:
    settings = Settings(
        robot_service_host="127.0.0.1",
        robot_service_port=8000,
        isaac_sim_root="/opt/isaacsim",
        runs_dir="robot_service/runs",  # type: ignore[arg-type]
        log_level="INFO",
    )
    return RobotServiceManager(
        settings=settings,
        worker_factory=lambda session_id, session_dir: handle,
    )


def wait_until(predicate, timeout: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Condition was not met before timeout")


def test_create_session_sends_environment_id_to_worker():
    handle = FakeWorkerHandle()
    manager = build_manager(handle)

    session = manager.create_session(
        CreateSessionRequest(backend_type="isaac_sim", environment_id="env-default")
    )

    assert session.session_status == "ready"
    assert handle.commands[0].command_type == "load_environment"
    assert handle.commands[0].payload["environment_id"] == "env-default"
    assert handle.timeouts[0] == manager._settings.worker_start_timeout_s


def test_create_session_rejects_second_active_session():
    handle = FakeWorkerHandle()
    manager = build_manager(handle)

    manager.create_session(
        CreateSessionRequest(backend_type="isaac_sim", environment_id="env-default")
    )

    with pytest.raises(RobotServiceConflictError):
        manager.create_session(
            CreateSessionRequest(backend_type="isaac_sim", environment_id="env-second")
        )


def test_create_task_runs_in_background_and_updates_to_succeeded():
    handle = FakeWorkerHandle()
    manager = build_manager(handle)
    session = manager.create_session(
        CreateSessionRequest(backend_type="isaac_sim", environment_id="env-default")
    )

    task = manager.create_task(
        session.session_id,
        CreateTaskRequest(
            task=TaskContent(
                task_id="task-1",
                instruction="Pick up the cube",
                object_texts=["cube"],
            ),
            policy_source="def run_policy(robot, perception_data):\n    return None",
            perception_data={"objects": []},
        ),
    )

    assert task.task_status == "queued"

    handle.wait_for_task_start()
    wait_until(
        lambda: manager.get_task(session.session_id, task.session_task_id).task_status == "running"
    )

    handle.finish_task("task_succeeded")

    wait_until(
        lambda: manager.get_task(session.session_id, task.session_task_id).task_status == "succeeded"
    )


def test_delete_session_rejects_while_task_is_running():
    handle = FakeWorkerHandle()
    manager = build_manager(handle)
    session = manager.create_session(
        CreateSessionRequest(backend_type="isaac_sim", environment_id="env-default")
    )
    task = manager.create_task(
        session.session_id,
        CreateTaskRequest(
            task=TaskContent(
                task_id="task-1",
                instruction="Pick up the cube",
                object_texts=["cube"],
            ),
            policy_source="def run_policy(robot, perception_data):\n    return None",
            perception_data={"objects": []},
        ),
    )

    handle.wait_for_task_start()
    wait_until(
        lambda: manager.get_task(session.session_id, task.session_task_id).task_status == "running"
    )

    with pytest.raises(RobotServiceConflictError):
        manager.delete_session(session.session_id)

    handle.finish_task("task_succeeded")


def test_get_cameras_registers_artifacts_in_manager_index():
    handle = FakeWorkerHandle()
    manager = build_manager(handle)
    session = manager.create_session(
        CreateSessionRequest(backend_type="isaac_sim", environment_id="env-default")
    )

    response = manager.get_cameras(session.session_id)

    assert len(response.cameras) == 2
    assert response.cameras[0].depth_image.artifact_id == "artifact-depth"
    assert response.cameras[1].depth_image.artifact_id == "artifact-depth-overview"
    assert manager.artifact_index["artifact-rgb"].content_type == "image/png"
    assert manager.artifact_index["artifact-depth"].content_type == "application/x-npy"
    assert manager.artifact_index["artifact-rgb-overview"].content_type == "image/png"
    assert manager.artifact_index["artifact-depth-overview"].content_type == "application/x-npy"


def test_subprocess_worker_handle_skips_non_json_stdout_lines(monkeypatch, tmp_path):
    class FakeProcess:
        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def kill(self) -> None:
            return None

    master_fd, slave_fd = pty.openpty()
    writer_fd = os.dup(slave_fd)

    def fake_openpty():
        return master_fd, slave_fd

    def fake_popen(*args, **kwargs):
        return FakeProcess()

    monkeypatch.setattr("robot_service.api.manager.pty.openpty", fake_openpty)
    monkeypatch.setattr("robot_service.api.manager.subprocess.Popen", fake_popen)

    settings = Settings(
        robot_service_host="127.0.0.1",
        robot_service_port=8000,
        isaac_sim_root="/root/isaacsim",
        runs_dir=tmp_path,
        log_level="INFO",
    )
    handle = SubprocessWorkerHandle(settings=settings, session_id="sess-demo", session_dir=tmp_path / "run")

    def emit_lines() -> None:
        time.sleep(0.01)
        os.write(writer_fd, b"[Info] Isaac Sim startup log\n")
        os.write(
            writer_fd,
            b'{"request_id":"req-1","event_type":"environment_loaded","payload":{"environment_id":"env-default"}}\n',
        )

    writer_thread = threading.Thread(target=emit_lines)
    writer_thread.start()

    event = handle.send(
        WorkerCommand(
            request_id="req-1",
            command_type="load_environment",
            payload={"environment_id": "env-default"},
        ),
        timeout_s=1.0,
    )

    assert event.event_type == "environment_loaded"
    assert event.payload["environment_id"] == "env-default"
    writer_thread.join()
    os.close(writer_fd)
    handle.close()


def test_subprocess_worker_handle_strips_ansi_prefix_from_json_lines(monkeypatch, tmp_path):
    class FakeProcess:
        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def kill(self) -> None:
            return None

    master_fd, slave_fd = pty.openpty()
    writer_fd = os.dup(slave_fd)

    def fake_openpty():
        return master_fd, slave_fd

    def fake_popen(*args, **kwargs):
        return FakeProcess()

    monkeypatch.setattr("robot_service.api.manager.pty.openpty", fake_openpty)
    monkeypatch.setattr("robot_service.api.manager.subprocess.Popen", fake_popen)

    settings = Settings(
        robot_service_host="127.0.0.1",
        robot_service_port=8000,
        isaac_sim_root="/root/isaacsim",
        runs_dir=tmp_path,
        log_level="INFO",
    )
    handle = SubprocessWorkerHandle(settings=settings, session_id="sess-demo", session_dir=tmp_path / "run")

    def emit_lines() -> None:
        time.sleep(0.01)
        os.write(
            writer_fd,
            b'\x1b[0m{"request_id":"req-ansi","event_type":"environment_loaded","payload":{"environment_id":"env-default"}}\n',
        )

    writer_thread = threading.Thread(target=emit_lines)
    writer_thread.start()

    event = handle.send(
        WorkerCommand(
            request_id="req-ansi",
            command_type="load_environment",
            payload={"environment_id": "env-default"},
        ),
        timeout_s=1.0,
    )

    assert event.event_type == "environment_loaded"
    assert event.payload["environment_id"] == "env-default"
    writer_thread.join()
    os.close(writer_fd)
    handle.close()
