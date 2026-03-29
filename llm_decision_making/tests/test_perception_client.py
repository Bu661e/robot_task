from __future__ import annotations

import importlib
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
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.content = content
        self.headers = headers or {}

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
        self.calls: list[dict[str, object]] = []
        FakeHTTPXClient.instances.append(self)

    def request(
        self,
        method: str,
        url: str,
        *,
        json: object | None = None,
        data: object | None = None,
        files: object | None = None,
    ) -> FakeHTTPXResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "json": json,
                "data": data,
                "files": files,
            }
        )
        if not FakeHTTPXClient.queued_responses:
            raise AssertionError("No queued fake response available.")
        return FakeHTTPXClient.queued_responses.pop(0)


def _build_perception_request() -> object:
    perception_schemas = importlib.import_module("utils.perception_schemas")
    return perception_schemas.PerceptionRequest(
        task=perception_schemas.PerceptionTask(
            task_id="1",
            instruction="Place the blue_cube on top of the red_cube",
            object_texts=["blue_cube", "red_cube"],
        ),
        observations=[
            perception_schemas.PerceptionObservation(
                camera_id="table_top",
                rgb_image=perception_schemas.ArtifactRef(
                    artifact_id="artifact_rgb_1",
                    content_type="image/png",
                ),
                depth_image=perception_schemas.ArtifactRef(
                    artifact_id="artifact_depth_1",
                    content_type="application/x-npy",
                ),
                intrinsics=perception_schemas.Intrinsics(
                    fx=533.33,
                    fy=533.33,
                    cx=320.0,
                    cy=320.0,
                    width=640,
                    height=640,
                ),
                extrinsics=perception_schemas.Extrinsics(
                    translation=[0.0, 0.0, 6.0],
                    quaternion_wxyz=[0.7071, 0.0, 0.7071, 0.0],
                ),
                timestamp="2026-03-29T02:52:29Z",
                ext={
                    "depth_unit": "meter",
                    "depth_encoding": "npy-float32",
                    "view_mode": "top_down",
                    "camera_frame_id": "camera_front",
                },
            )
        ],
        context=perception_schemas.PerceptionContext(
            session_id="sess_1",
            environment_id="env-default",
        ),
        options=perception_schemas.PerceptionOptions(
            include_mask_artifacts=True,
            include_visualization_artifacts=True,
            include_debug_artifacts=False,
            include_mesh_glb_artifacts=True,
            include_gaussian_ply_artifacts=True,
            include_pointcloud_artifacts=False,
            max_objects_per_label=4,
        ),
        ext={},
    )


def _perception_infer_response_payload() -> dict[str, object]:
    return {
        "request_id": "perc_req_1",
        "success": True,
        "timestamp": "2026-03-29T03:00:00Z",
        "observation_results": [
            {
                "camera_id": "table_top",
                "observation_timestamp": "2026-03-29T02:52:29Z",
                "success": True,
                "coordinate_frame": "camera",
                "detected_objects": [
                    {
                        "instance_id": "obj_blue_cube_0001",
                        "label": "blue_cube",
                        "source_object_text": "blue_cube",
                        "score": 0.96,
                        "source_mask_artifact_id": "artifact_mask_1",
                        "bbox_2d_xyxy": [122, 188, 214, 286],
                        "translation_m": [0.51, 0.12, 0.83],
                        "quaternion_wxyz": [0.998, 0.012, 0.05, -0.021],
                        "scale_m": [0.045, 0.045, 0.045],
                        "mesh_glb_artifact_id": "artifact_mesh_1",
                        "gaussian_ply_artifact_id": "artifact_gaussian_1",
                        "pointcloud_artifact_id": None,
                        "ext": {},
                    }
                ],
                "scene_artifacts": {
                    "visualization_artifact_ids": ["artifact_vis_1"],
                    "debug_artifact_ids": [],
                },
                "error": {},
                "ext": {},
            }
        ],
        "error": {},
        "ext": {},
    }


def test_default_perception_client_uses_shared_perception_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PERCEPTION_BASE_URL", "https://perception.example.com")
    monkeypatch.setenv("PERCEPTION_TIMEOUT_S", "12.5")
    monkeypatch.setenv("PERCEPTION_TRUST_ENV", "true")

    perception_config_module = importlib.import_module("config.perception_config")
    perception_config_module = importlib.reload(perception_config_module)
    perception_client_module = importlib.import_module("utils.perception_client")
    perception_client_module = importlib.reload(perception_client_module)

    assert perception_client_module.default_perception_client._base_url == (
        "https://perception.example.com"
    )
    assert perception_client_module.default_perception_client._timeout_s == 12.5
    assert perception_client_module.default_perception_client._trust_env is True


def test_perception_request_to_dict_serializes_observations() -> None:
    request = _build_perception_request()

    payload = request.to_dict()

    assert payload["task"]["object_texts"] == ["blue_cube", "red_cube"]
    assert payload["observations"][0]["camera_id"] == "table_top"
    assert payload["observations"][0]["depth_image"]["artifact_id"] == "artifact_depth_1"
    assert payload["observations"][0]["extrinsics"]["quaternion_wxyz"] == [
        0.7071,
        0.0,
        0.7071,
        0.0,
    ]


def test_perception_response_from_dict_parses_detected_objects() -> None:
    perception_schemas = importlib.import_module("utils.perception_schemas")

    response = perception_schemas.PerceptionResponse.from_dict(
        _perception_infer_response_payload()
    )

    assert response.request_id == "perc_req_1"
    assert response.success is True
    assert response.observation_results[0].camera_id == "table_top"
    assert response.observation_results[0].detected_objects[0].label == "blue_cube"
    assert response.observation_results[0].detected_objects[0].mesh_glb_artifact_id == (
        "artifact_mesh_1"
    )


def test_perception_client_upload_artifact_posts_multipart_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("utils.perception_client.httpx.Client", FakeHTTPXClient)
    FakeHTTPXClient.instances = []
    FakeHTTPXClient.queued_responses = [
        FakeHTTPXResponse(
            status_code=201,
            json_data={
                "artifact_id": "artifact_rgb_1",
                "artifact_type": "rgb_image",
                "content_type": "image/png",
                "filename": "front_rgb.png",
                "size_bytes": 9,
                "sha256": "abc123",
                "created_at": "2026-03-29T03:00:00Z",
                "ext": {},
            },
        )
    ]

    perception_client_module = importlib.import_module("utils.perception_client")
    client = perception_client_module.PerceptionClient(
        base_url="https://perception.example.com",
        timeout_s=15.0,
        trust_env=False,
    )

    response = client.upload_artifact(
        filename="front_rgb.png",
        content=b"png-bytes",
        artifact_type="rgb_image",
        content_type="image/png",
    )

    assert response.artifact_id == "artifact_rgb_1"
    assert FakeHTTPXClient.instances[0].calls == [
        {
            "method": "POST",
            "url": "/artifacts",
            "json": None,
            "data": {
                "artifact_type": "rgb_image",
                "ext": "{}",
            },
            "files": {
                "file": ("front_rgb.png", b"png-bytes", "image/png"),
            },
        }
    ]


def test_perception_client_infer_posts_typed_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("utils.perception_client.httpx.Client", FakeHTTPXClient)
    FakeHTTPXClient.instances = []
    FakeHTTPXClient.queued_responses = [
        FakeHTTPXResponse(
            status_code=200,
            json_data=_perception_infer_response_payload(),
        )
    ]

    perception_client_module = importlib.import_module("utils.perception_client")
    client = perception_client_module.PerceptionClient(
        base_url="https://perception.example.com",
        timeout_s=15.0,
        trust_env=False,
    )
    request = _build_perception_request()

    response = client.infer(request)

    assert response.request_id == "perc_req_1"
    assert FakeHTTPXClient.instances[0].calls == [
        {
            "method": "POST",
            "url": "/perception/infer",
            "json": request.to_dict(),
            "data": None,
            "files": None,
        }
    ]


def test_perception_client_download_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("utils.perception_client.httpx.Client", FakeHTTPXClient)
    FakeHTTPXClient.instances = []
    FakeHTTPXClient.queued_responses = [
        FakeHTTPXResponse(
            status_code=200,
            content=b"png-bytes",
            headers={"content-type": "image/png"},
        )
    ]

    perception_client_module = importlib.import_module("utils.perception_client")
    client = perception_client_module.PerceptionClient(
        base_url="https://perception.example.com",
        timeout_s=15.0,
        trust_env=False,
    )

    response = client.download_artifact("artifact_vis_1")

    assert response == b"png-bytes"
    assert FakeHTTPXClient.instances[0].calls == [
        {
            "method": "GET",
            "url": "/artifacts/artifact_vis_1/content",
            "json": None,
            "data": None,
            "files": None,
        }
    ]


def test_perception_client_raises_for_error_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("utils.perception_client.httpx.Client", FakeHTTPXClient)
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

    perception_client_module = importlib.import_module("utils.perception_client")
    client = perception_client_module.PerceptionClient(
        base_url="https://perception.example.com",
        timeout_s=15.0,
        trust_env=False,
    )
    request = _build_perception_request()

    with pytest.raises(perception_client_module.PerceptionClientError, match="NOT_FOUND"):
        client.infer(request)


def test_perception_client_rejects_non_object_json_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("utils.perception_client.httpx.Client", FakeHTTPXClient)
    FakeHTTPXClient.instances = []
    FakeHTTPXClient.queued_responses = [
        FakeHTTPXResponse(
            status_code=200,
            json_data=["not", "an", "object"],
        )
    ]

    perception_client_module = importlib.import_module("utils.perception_client")
    client = perception_client_module.PerceptionClient(
        base_url="https://perception.example.com",
        timeout_s=15.0,
        trust_env=False,
    )
    request = _build_perception_request()

    with pytest.raises(
        perception_client_module.PerceptionClientError,
        match="must be a JSON object",
    ):
        client.infer(request)


def test_perception_client_logs_json_requests_and_responses_when_run_logger_is_active(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("utils.perception_client.httpx.Client", FakeHTTPXClient)
    FakeHTTPXClient.instances = []
    FakeHTTPXClient.queued_responses = [
        FakeHTTPXResponse(
            status_code=200,
            json_data=_perception_infer_response_payload(),
        )
    ]
    run_logger = start_run_logging(
        task_id="1",
        base_dir=tmp_path,
        started_at=datetime(2026, 3, 29, 3, 0, 0),
    )

    perception_client_module = importlib.import_module("utils.perception_client")
    client = perception_client_module.PerceptionClient(
        base_url="https://perception.example.com",
        timeout_s=15.0,
        trust_env=False,
    )
    request = _build_perception_request()

    response = client.infer(request)
    captured = capsys.readouterr()
    request_files = sorted((run_logger.root_dir / "perception_service" / "requests").glob("*.json"))
    response_files = sorted((run_logger.root_dir / "perception_service" / "responses").glob("*.json"))

    assert response.request_id == "perc_req_1"
    assert len(request_files) == 1
    assert len(response_files) == 1
    assert json.loads(request_files[0].read_text(encoding="utf-8"))["body"] == request.to_dict()
    assert (
        json.loads(response_files[0].read_text(encoding="utf-8"))["body"]["request_id"]
        == "perc_req_1"
    )
    assert "POST /perception/infer" in captured.err
    assert "blue_cube" not in captured.err

    clear_active_run_logger()


def test_perception_client_download_artifact_persists_binary_response_when_run_logger_is_active(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("utils.perception_client.httpx.Client", FakeHTTPXClient)
    FakeHTTPXClient.instances = []
    FakeHTTPXClient.queued_responses = [
        FakeHTTPXResponse(
            status_code=200,
            content=b"png-bytes",
            headers={"content-type": "image/png"},
        )
    ]
    run_logger = start_run_logging(
        task_id="1",
        base_dir=tmp_path,
        started_at=datetime(2026, 3, 29, 3, 0, 0),
    )

    perception_client_module = importlib.import_module("utils.perception_client")
    client = perception_client_module.PerceptionClient(
        base_url="https://perception.example.com",
        timeout_s=15.0,
        trust_env=False,
    )

    response = client.download_artifact("artifact_vis_1")
    captured = capsys.readouterr()
    response_files = sorted((run_logger.root_dir / "perception_service" / "responses").glob("*.json"))
    artifact_path = run_logger.root_dir / "perception_service" / "artifacts" / "artifact_vis_1.png"

    assert response == b"png-bytes"
    assert artifact_path.read_bytes() == b"png-bytes"
    assert json.loads(response_files[0].read_text(encoding="utf-8"))["body"] == {
        "artifact_path": "perception_service/artifacts/artifact_vis_1.png",
        "size_bytes": 9,
    }
    assert "artifact_vis_1" in captured.err
    assert "size_bytes=9" in captured.err
    assert "png-bytes" not in captured.err

    clear_active_run_logger()
