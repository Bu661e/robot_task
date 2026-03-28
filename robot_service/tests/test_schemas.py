import pytest
from pydantic import ValidationError

from robot_service.common.messages import WorkerCommand, WorkerEvent
from robot_service.common.schemas import CameraPayload, CreateSessionRequest, CreateTaskRequest, TaskContent


def test_create_session_request_strips_environment_id_and_defaults_ext():
    request = CreateSessionRequest(backend_type="isaac_sim", environment_id="  env-demo  ")

    assert request.environment_id == "env-demo"
    assert request.ext == {}


def test_create_task_request_defaults_ext_and_keeps_nested_task():
    request = CreateTaskRequest(
        task=TaskContent(
            task_id="1",
            instruction="Pick up the cube",
            object_texts=["cube"],
        ),
        policy_source="def run_policy(robot, perception_data):\n    return None",
        perception_data={"objects": []},
    )

    assert request.task.task_id == "1"
    assert request.ext == {}


def test_create_session_request_rejects_blank_environment_id():
    with pytest.raises(ValidationError):
        CreateSessionRequest(backend_type="isaac_sim", environment_id="   ")


def test_worker_command_and_event_support_json_roundtrip():
    command = WorkerCommand(
        request_id="req-1",
        command_type="load_environment",
        payload={"environment_id": "env-demo"},
    )
    event = WorkerEvent(
        request_id="req-1",
        event_type="environment_loaded",
        payload={"environment_id": "env-demo"},
    )

    assert WorkerCommand.model_validate_json(command.model_dump_json()) == command
    assert WorkerEvent.model_validate_json(event.model_dump_json()) == event


def test_camera_payload_requires_depth_image():
    with pytest.raises(ValidationError):
        CameraPayload.model_validate(
            {
                "camera_id": "table_top",
                "rgb_image": {"artifact_id": "artifact-rgb", "content_type": "image/png"},
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
                    "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
                },
            }
        )
