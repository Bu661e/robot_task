from robot_service.common.schemas import ArtifactRecord, ArtifactRef, CameraExtrinsics, CameraIntrinsics, CameraPayload, CreateTaskRequest, TaskContent
from robot_service.worker.environment import EnvironmentRuntime
from robot_service.worker.queries import build_action_apis_payload, build_cameras_payload, build_robot_status
from robot_service.worker.task_runner import TaskRunner


def test_environment_runtime_tracks_environment_id_and_default_assets():
    runtime = EnvironmentRuntime()

    runtime.load_environment("env-default")

    assert runtime.current_environment_id == "env-default"
    assert runtime.scene_assets == [
        "ground",
        "light",
        "table",
        "franka",
        "camera",
        "red_cube_1",
        "red_cube_2",
        "blue_cube_1",
        "blue_cube_2",
    ]
    assert runtime.world is None


def test_environment_runtime_uses_isaac_loader_when_simulation_app_is_present(monkeypatch):
    runtime = EnvironmentRuntime(simulation_app=object())

    def fake_load_isaac_scene(environment_id: str) -> None:
        assert environment_id == "env-default"
        runtime.scene_assets = ["ground", "light", "table", "franka", "camera"]
        runtime.world = object()

    monkeypatch.setattr(runtime, "_load_isaac_scene", fake_load_isaac_scene)

    runtime.load_environment("env-default")

    assert runtime.current_environment_id == "env-default"
    assert runtime.scene_assets == ["ground", "light", "table", "franka", "camera"]
    assert runtime.world is not None


def test_query_builders_return_placeholder_robot_and_action_api_data():
    runtime = EnvironmentRuntime()
    runtime.load_environment("env-default")

    robot_status = build_robot_status("sess-demo", runtime)
    action_apis = build_action_apis_payload("sess-demo", runtime)

    assert robot_status.robot_status == "ready"
    assert action_apis.action_apis == ["robot.pick_and_place(pick_position, place_position, rotation=None)"]


def test_build_cameras_payload_returns_artifact_backed_depth_camera():
    runtime = EnvironmentRuntime(current_environment_id="env-default")
    rgb_record = ArtifactRecord(
        artifact_id="artifact-rgb",
        session_id="sess-demo",
        content_type="image/png",
        file_path="/tmp/artifact-rgb.png",
    )
    depth_record = ArtifactRecord(
        artifact_id="artifact-depth",
        session_id="sess-demo",
        content_type="application/x-npy",
        file_path="/tmp/artifact-depth.npy",
    )
    runtime.capture_camera_payloads = lambda session_id: (  # type: ignore[method-assign]
        [
            CameraPayload(
                camera_id="table_top",
                rgb_image=ArtifactRef(artifact_id="artifact-rgb", content_type="image/png"),
                depth_image=ArtifactRef(artifact_id="artifact-depth", content_type="application/x-npy"),
                intrinsics=CameraIntrinsics(
                    fx=500.0,
                    fy=510.0,
                    cx=320.0,
                    cy=240.0,
                    width=640,
                    height=480,
                ),
                extrinsics=CameraExtrinsics(
                    translation=[0.0, 0.0, 3.0],
                    quaternion_xyzw=[0.0, 0.0, 0.0, 1.0],
                ),
                ext={"depth_encoding": "npy-float32"},
            )
        ],
        [rgb_record, depth_record],
        {"environment_id": session_id},
    )

    response, artifact_records = build_cameras_payload("sess-demo", runtime)

    assert len(response.cameras) == 1
    camera = response.cameras[0]
    assert camera.camera_id == "table_top"
    assert camera.rgb_image.artifact_id == "artifact-rgb"
    assert camera.depth_image.artifact_id == "artifact-depth"
    assert camera.extrinsics.translation == [0.0, 0.0, 3.0]
    assert camera.extrinsics.quaternion_xyzw == [0.0, 0.0, 0.0, 1.0]
    assert camera.ext["depth_encoding"] == "npy-float32"
    assert artifact_records == [rgb_record, depth_record]


def test_task_runner_returns_succeeded_placeholder_result():
    runtime = EnvironmentRuntime()
    runtime.load_environment("env-default")
    runner = TaskRunner(runtime)

    event = runner.run_task(
        session_id="sess-demo",
        session_task_id="task-demo",
        request=CreateTaskRequest(
            task=TaskContent(
                task_id="task-1",
                instruction="Pick up the cube",
                object_texts=["cube"],
            ),
            policy_source="def run_policy(robot, perception_data):\n    return None",
            perception_data={"objects": []},
        ),
    )

    assert event.event_type == "task_succeeded"
