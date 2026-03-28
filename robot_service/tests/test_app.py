from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from robot_service.api.app import create_app
from robot_service.api.manager import RobotServiceManager
from robot_service.common.messages import WorkerEvent
from robot_service.common.schemas import ArtifactRecord
from robot_service.runtime.settings import Settings


class FakeWorkerHandle:
    def __init__(self) -> None:
        self.commands = []
        self._closed = False

    def send(self, command, timeout_s: float) -> WorkerEvent:
        del timeout_s
        self.commands.append(command)
        if command.command_type == "load_environment":
            return WorkerEvent(
                request_id=command.request_id,
                event_type="environment_loaded",
                payload={"environment_id": command.payload["environment_id"]},
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
                                "translation": [0.0, 3.3, 3.3],
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
        raise AssertionError(f"Unexpected command type: {command.command_type}")

    def close(self) -> None:
        self._closed = True

    def is_alive(self) -> bool:
        return not self._closed

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


def test_get_robot_and_cameras_return_first_phase_payloads():
    client, _ = create_test_client()
    session = client.post(
        "/sessions",
        json={"backend_type": "isaac_sim", "environment_id": "env-default"},
    ).json()

    robot_response = client.get(f"/sessions/{session['session_id']}/robot")
    cameras_response = client.get(f"/sessions/{session['session_id']}/cameras")

    assert robot_response.status_code == 200
    assert robot_response.json()["robot_status"] == "ready"
    assert cameras_response.status_code == 200
    cameras = cameras_response.json()["cameras"]
    assert len(cameras) == 2
    assert cameras[0]["camera_id"] == "table_top"
    assert cameras[0]["depth_image"]["artifact_id"] == "artifact-depth"
    assert cameras[0]["intrinsics"]["width"] == 640
    assert cameras[0]["intrinsics"]["height"] == 640
    assert cameras[1]["camera_id"] == "table_overview"
    assert cameras[1]["depth_image"]["artifact_id"] == "artifact-depth-overview"
    assert cameras[1]["intrinsics"]["width"] == 640
    assert cameras[1]["intrinsics"]["height"] == 640


def test_second_phase_routes_are_not_exposed_in_first_phase():
    client, _ = create_test_client()
    session = client.post(
        "/sessions",
        json={"backend_type": "isaac_sim", "environment_id": "env-default"},
    ).json()

    action_apis = client.get(f"/sessions/{session['session_id']}/action-apis")
    create_task = client.post(f"/sessions/{session['session_id']}/tasks", json={})
    list_tasks = client.get(f"/sessions/{session['session_id']}/tasks")

    assert action_apis.status_code == 404
    assert create_task.status_code == 404
    assert list_tasks.status_code == 404


def test_download_artifact_returns_binary_file(tmp_path):
    handle = FakeWorkerHandle()
    manager = RobotServiceManager(
        settings=Settings(
            robot_service_host="127.0.0.1",
            robot_service_port=8000,
            isaac_sim_root="/opt/isaacsim",
            runs_dir=tmp_path,
            log_level="INFO",
        ),
        worker_factory=lambda session_id, session_dir: handle,
    )
    artifact_path = tmp_path / "artifact.png"
    artifact_bytes = b"fake-png-bytes"
    artifact_path.write_bytes(artifact_bytes)
    manager.artifact_index["artifact-demo"] = ArtifactRecord(
        artifact_id="artifact-demo",
        session_id="sess-demo",
        content_type="image/png",
        file_path=str(Path(artifact_path)),
    )
    client = TestClient(create_app(manager))

    response = client.get("/artifacts/artifact-demo")

    assert response.status_code == 200
    assert response.content == artifact_bytes
    assert response.headers["content-type"] == "image/png"
