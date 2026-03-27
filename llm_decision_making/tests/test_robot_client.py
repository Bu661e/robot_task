from __future__ import annotations

import importlib

import pytest


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
                "environment_id": "2-ycb",
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

    response = client.create_session(environment_id="2-ycb")

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
                "environment_id": "2-ycb",
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
                "environment_id": "2-ycb",
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

    assert response.environment_id == "2-ycb"
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

    response = client.download_artifact(artifact_id="artifact_rgb_1")

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
