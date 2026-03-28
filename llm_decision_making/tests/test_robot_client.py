from __future__ import annotations

import importlib
import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pytest

from utils.run_logging import clear_active_run_logger, start_run_logging


class FakeHTTPXResponse:
    def __init__(
        self,
        *,
        status_code: int,
        json_data: object | None = None,
        content: bytes = b"",
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.content = content

    def json(self) -> object:
        if self._json_data is None:
            raise ValueError("response does not contain JSON data")
        return self._json_data


class FakeHTTPXClient:
    instances: list[FakeHTTPXClient] = []
    queued_responses: list[FakeHTTPXResponse] = []

    def __init__(self, *, base_url: str, timeout: float, trust_env: bool) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.trust_env = trust_env
        self.calls: list[tuple[str, str, object | None]] = []
        FakeHTTPXClient.instances.append(self)

    def request(
        self,
        method: str,
        url: str,
        *,
        json: object | None = None,
    ) -> FakeHTTPXResponse:
        self.calls.append((method, url, json))
        if not FakeHTTPXClient.queued_responses:
            raise AssertionError("No queued fake response available.")
        return FakeHTTPXClient.queued_responses.pop(0)


def test_default_robot_client_uses_shared_robot_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("httpx.Client", FakeHTTPXClient)
    monkeypatch.setenv("ROBOT_BASE_URL", "https://robot.example.com")
    monkeypatch.setenv("ROBOT_BACKEND_TYPE", "isaac_sim")
    monkeypatch.setenv("ROBOT_TIMEOUT_S", "12.5")
    monkeypatch.setenv("ROBOT_TRUST_ENV", "true")

    robot_config_module = importlib.import_module("config.robot_config")
    robot_config_module = importlib.reload(robot_config_module)
    robot_client_module = importlib.import_module("utils.robot_client")
    robot_client_module = importlib.reload(robot_client_module)

    assert robot_client_module.default_robot_client._base_url == "https://robot.example.com"
    assert robot_client_module.default_robot_client._backend_type == "isaac_sim"
    assert robot_client_module.default_robot_client._timeout_s == 12.5
    assert robot_client_module.default_robot_client._trust_env is True


def test_default_robot_client_uses_remote_robot_service_base_url_when_env_not_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ROBOT_BASE_URL", raising=False)
    monkeypatch.delenv("ROBOT_BACKEND_TYPE", raising=False)
    monkeypatch.delenv("ROBOT_TIMEOUT_S", raising=False)
    monkeypatch.delenv("ROBOT_TRUST_ENV", raising=False)

    robot_config_module = importlib.import_module("config.robot_config")
    robot_config_module = importlib.reload(robot_config_module)
    robot_client_module = importlib.import_module("utils.robot_client")
    robot_client_module = importlib.reload(robot_client_module)

    assert robot_config_module.ROBOT_BASE_URL == (
        "https://vsq4t8n3-wteq1vxp-18080.ahrestapi.gpufree.cn:8443"
    )
    assert robot_client_module.default_robot_client._base_url == (
        "https://vsq4t8n3-wteq1vxp-18080.ahrestapi.gpufree.cn:8443"
    )


def test_robot_schemas_parse_camera_depth_image_in_ext() -> None:
    robot_schemas_module = importlib.import_module("utils.robot_schemas")
    response = robot_schemas_module.CameraObservationResponse.from_dict(
        {
            "session_id": "sess_1",
            "timestamp": "2026-03-28T10:00:00Z",
            "cameras": [
                {
                    "camera_id": "front",
                    "rgb_image": {
                        "content_type": "image/png",
                        "artifact_id": "artifact_rgb_1",
                    },
                    "intrinsics": {
                        "fx": 1.0,
                        "fy": 2.0,
                        "cx": 3.0,
                        "cy": 4.0,
                        "width": 640,
                        "height": 480,
                    },
                    "extrinsics": {
                        "translation": [0.0, 0.0, 1.0],
                        "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
                    },
                    "ext": {
                        "depth_image": {
                            "content_type": "image/png",
                            "artifact_id": "artifact_depth_1",
                        }
                    },
                }
            ],
            "ext": {},
        }
    )

    assert response.cameras[0].rgb_image.artifact_id == "artifact_rgb_1"
    assert response.cameras[0].ext.depth_image is not None
    assert response.cameras[0].ext.depth_image.artifact_id == "artifact_depth_1"


def test_robot_schemas_parse_camera_depth_image_at_top_level() -> None:
    robot_schemas_module = importlib.import_module("utils.robot_schemas")
    response = robot_schemas_module.CameraObservationResponse.from_dict(
        {
            "session_id": "sess_1",
            "timestamp": "2026-03-28T10:00:00Z",
            "cameras": [
                {
                    "camera_id": "front",
                    "rgb_image": {
                        "content_type": "image/png",
                        "artifact_id": "artifact_rgb_1",
                    },
                    "depth_image": {
                        "content_type": "application/x-npy",
                        "artifact_id": "artifact_depth_1",
                    },
                    "intrinsics": {
                        "fx": 1.0,
                        "fy": 2.0,
                        "cx": 3.0,
                        "cy": 4.0,
                        "width": 640,
                        "height": 480,
                    },
                    "extrinsics": {
                        "translation": [0.0, 0.0, 1.0],
                        "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
                    },
                    "ext": {},
                }
            ],
            "ext": {},
        }
    )

    assert response.cameras[0].rgb_image.artifact_id == "artifact_rgb_1"
    assert response.cameras[0].ext.depth_image is not None
    assert response.cameras[0].ext.depth_image.artifact_id == "artifact_depth_1"


def test_robot_schema_module_alias_is_not_present() -> None:
    assert importlib.util.find_spec("utils.robot_schema") is None


def test_robot_client_create_session_posts_backend_and_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("utils.robot_client.httpx.Client", FakeHTTPXClient)
    FakeHTTPXClient.instances = []
    FakeHTTPXClient.queued_responses = [
        FakeHTTPXResponse(
            status_code=200,
            json_data={
                "session_id": "sess_1",
                "session_status": "ready",
                "backend_type": "isaac_sim",
                "environment_id": "env-default",
                "ext": {},
            },
        )
    ]

    from utils.robot_client import RobotClient

    client = RobotClient(
        base_url="https://robot.example.com",
        backend_type="isaac_sim",
        timeout_s=15.0,
        trust_env=False,
    )

    response = client.create_session(environment_id="env-default")

    assert response.session_id == "sess_1"
    assert FakeHTTPXClient.instances[0].base_url == "https://robot.example.com"
    assert FakeHTTPXClient.instances[0].timeout == 15.0
    assert FakeHTTPXClient.instances[0].trust_env is False
    assert FakeHTTPXClient.instances[0].calls == [
        (
            "POST",
            "/sessions",
            {
                "backend_type": "isaac_sim",
                "environment_id": "env-default",
                "ext": {},
            },
        )
    ]


def test_robot_client_get_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("utils.robot_client.httpx.Client", FakeHTTPXClient)
    FakeHTTPXClient.instances = []
    FakeHTTPXClient.queued_responses = [
        FakeHTTPXResponse(
            status_code=200,
            json_data={
                "session_id": "sess_1",
                "session_status": "ready",
                "backend_type": "isaac_sim",
                "environment_id": "env-default",
                "ext": {},
            },
        )
    ]

    from utils.robot_client import RobotClient

    client = RobotClient(
        base_url="https://robot.example.com",
        backend_type="isaac_sim",
        timeout_s=15.0,
        trust_env=False,
    )

    response = client.get_session(session_id="sess_1")

    assert response.environment_id == "env-default"
    assert FakeHTTPXClient.instances[0].calls == [("GET", "/sessions/sess_1", None)]


def test_robot_client_close_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("utils.robot_client.httpx.Client", FakeHTTPXClient)
    FakeHTTPXClient.instances = []
    FakeHTTPXClient.queued_responses = [
        FakeHTTPXResponse(
            status_code=200,
            json_data={
                "session_id": "sess_1",
                "session_status": "stopped",
                "ext": {},
            },
        )
    ]

    from utils.robot_client import RobotClient

    client = RobotClient(
        base_url="https://robot.example.com",
        backend_type="isaac_sim",
        timeout_s=15.0,
        trust_env=False,
    )

    response = client.close_session(session_id="sess_1")

    assert response.session_status == "stopped"
    assert FakeHTTPXClient.instances[0].calls == [("DELETE", "/sessions/sess_1", None)]


def test_robot_client_get_robot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("utils.robot_client.httpx.Client", FakeHTTPXClient)
    FakeHTTPXClient.instances = []
    FakeHTTPXClient.queued_responses = [
        FakeHTTPXResponse(
            status_code=200,
            json_data={
                "session_id": "sess_1",
                "timestamp": "2026-03-28T10:00:00Z",
                "robot_status": "ready",
                "ext": {},
            },
        )
    ]

    from utils.robot_client import RobotClient

    client = RobotClient(
        base_url="https://robot.example.com",
        backend_type="isaac_sim",
        timeout_s=15.0,
        trust_env=False,
    )

    response = client.get_robot(session_id="sess_1")

    assert response.robot_status == "ready"
    assert FakeHTTPXClient.instances[0].calls == [("GET", "/sessions/sess_1/robot", None)]


def test_robot_client_get_cameras(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("utils.robot_client.httpx.Client", FakeHTTPXClient)
    FakeHTTPXClient.instances = []
    FakeHTTPXClient.queued_responses = [
        FakeHTTPXResponse(
            status_code=200,
            json_data={
                "session_id": "sess_1",
                "timestamp": "2026-03-28T10:00:00Z",
                "cameras": [
                    {
                        "camera_id": "front",
                        "rgb_image": {
                            "content_type": "image/png",
                            "artifact_id": "artifact_rgb_1",
                        },
                        "intrinsics": {
                            "fx": 1.0,
                            "fy": 2.0,
                            "cx": 3.0,
                            "cy": 4.0,
                            "width": 640,
                            "height": 480,
                        },
                        "extrinsics": {
                            "translation": [0.0, 0.0, 1.0],
                            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
                        },
                        "ext": {},
                    }
                ],
                "ext": {},
            },
        )
    ]

    from utils.robot_client import RobotClient

    client = RobotClient(
        base_url="https://robot.example.com",
        backend_type="isaac_sim",
        timeout_s=15.0,
        trust_env=False,
    )

    response = client.get_cameras(session_id="sess_1")

    assert response.cameras[0].camera_id == "front"
    assert response.cameras[0].rgb_image.artifact_id == "artifact_rgb_1"
    assert FakeHTTPXClient.instances[0].calls == [("GET", "/sessions/sess_1/cameras", None)]


def test_robot_client_download_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("utils.robot_client.httpx.Client", FakeHTTPXClient)
    FakeHTTPXClient.instances = []
    FakeHTTPXClient.queued_responses = [
        FakeHTTPXResponse(status_code=200, content=b"png-bytes")
    ]

    from utils.robot_client import RobotClient

    client = RobotClient(
        base_url="https://robot.example.com",
        backend_type="isaac_sim",
        timeout_s=15.0,
        trust_env=False,
    )

    response = client.download_artifact(
        artifact_id="artifact_rgb_1",
        content_type="image/png",
    )

    assert response == b"png-bytes"
    assert FakeHTTPXClient.instances[0].calls == [("GET", "/artifacts/artifact_rgb_1", None)]


def test_robot_client_raises_for_error_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("utils.robot_client.httpx.Client", FakeHTTPXClient)
    FakeHTTPXClient.instances = []
    FakeHTTPXClient.queued_responses = [
        FakeHTTPXResponse(
            status_code=404,
            json_data={
                "error_code": "NOT_FOUND",
                "message": "Requested resource not found.",
                "ext": {},
            },
        )
    ]

    from utils.robot_client import RobotClient, RobotClientError

    client = RobotClient(
        base_url="https://robot.example.com",
        backend_type="isaac_sim",
        timeout_s=15.0,
        trust_env=False,
    )

    with pytest.raises(RobotClientError, match="NOT_FOUND"):
        client.get_session(session_id="missing")


def test_robot_client_logs_json_requests_and_responses_when_run_logger_is_active(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("utils.robot_client.httpx.Client", FakeHTTPXClient)
    FakeHTTPXClient.instances = []
    FakeHTTPXClient.queued_responses = [
        FakeHTTPXResponse(
            status_code=200,
            json_data={
                "session_id": "sess_1",
                "session_status": "ready",
                "backend_type": "isaac_sim",
                "environment_id": "env-default",
                "ext": {},
            },
        )
    ]
    run_logger = start_run_logging(
        task_id="1",
        base_dir=tmp_path,
        started_at=datetime(2026, 3, 28, 16, 30, 45),
    )

    from utils.robot_client import RobotClient

    client = RobotClient(
        base_url="https://robot.example.com",
        backend_type="isaac_sim",
        timeout_s=15.0,
        trust_env=False,
    )

    response = client.create_session(environment_id="env-default")
    captured = capsys.readouterr()
    request_files = sorted((run_logger.root_dir / "robot_service" / "requests").glob("*.json"))
    response_files = sorted((run_logger.root_dir / "robot_service" / "responses").glob("*.json"))

    assert response.session_id == "sess_1"
    assert len(request_files) == 1
    assert len(response_files) == 1
    assert json.loads(request_files[0].read_text(encoding="utf-8"))["body"] == {
        "backend_type": "isaac_sim",
        "environment_id": "env-default",
        "ext": {},
    }
    assert json.loads(response_files[0].read_text(encoding="utf-8"))["body"]["session_id"] == "sess_1"
    assert "POST /sessions" in captured.err
    assert "backend_type" not in captured.err

    clear_active_run_logger()


def test_robot_client_download_artifact_persists_binary_response_when_run_logger_is_active(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("utils.robot_client.httpx.Client", FakeHTTPXClient)
    FakeHTTPXClient.instances = []
    FakeHTTPXClient.queued_responses = [
        FakeHTTPXResponse(status_code=200, content=b"png-bytes")
    ]
    run_logger = start_run_logging(
        task_id="1",
        base_dir=tmp_path,
        started_at=datetime(2026, 3, 28, 16, 30, 45),
    )

    from utils.robot_client import RobotClient

    client = RobotClient(
        base_url="https://robot.example.com",
        backend_type="isaac_sim",
        timeout_s=15.0,
        trust_env=False,
    )

    response = client.download_artifact(
        artifact_id="artifact_rgb_1",
        content_type="image/png",
    )
    captured = capsys.readouterr()
    request_files = sorted((run_logger.root_dir / "robot_service" / "requests").glob("*.json"))
    response_files = sorted((run_logger.root_dir / "robot_service" / "responses").glob("*.json"))
    artifact_path = run_logger.root_dir / "robot_service" / "artifacts" / "artifact_rgb_1.png"

    assert response == b"png-bytes"
    assert len(request_files) == 1
    assert len(response_files) == 1
    assert artifact_path.read_bytes() == b"png-bytes"
    assert json.loads(response_files[0].read_text(encoding="utf-8"))["body"] == {
        "artifact_path": "robot_service/artifacts/artifact_rgb_1.png",
        "size_bytes": 9,
    }
    assert "artifact_rgb_1" in captured.err
    assert "size_bytes=9" in captured.err
    assert "png-bytes" not in captured.err

    clear_active_run_logger()


def test_robot_client_download_depth_artifact_uses_npy_suffix_when_run_logger_is_active(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("utils.robot_client.httpx.Client", FakeHTTPXClient)
    FakeHTTPXClient.instances = []
    FakeHTTPXClient.queued_responses = [
        FakeHTTPXResponse(status_code=200, content=b"npy-bytes")
    ]
    run_logger = start_run_logging(
        task_id="1",
        base_dir=tmp_path,
        started_at=datetime(2026, 3, 28, 16, 30, 45),
    )

    from utils.robot_client import RobotClient

    client = RobotClient(
        base_url="https://robot.example.com",
        backend_type="isaac_sim",
        timeout_s=15.0,
        trust_env=False,
    )

    response = client.download_artifact(
        artifact_id="artifact_depth_1",
        content_type="application/x-npy",
    )
    response_files = sorted((run_logger.root_dir / "robot_service" / "responses").glob("*.json"))
    artifact_path = run_logger.root_dir / "robot_service" / "artifacts" / "artifact_depth_1.npy"

    assert response == b"npy-bytes"
    assert artifact_path.read_bytes() == b"npy-bytes"
    assert json.loads(response_files[0].read_text(encoding="utf-8"))["body"] == {
        "artifact_path": "robot_service/artifacts/artifact_depth_1.npy",
        "size_bytes": 9,
    }

    clear_active_run_logger()
