from robot_service.common.schemas import CreateTaskRequest, TaskContent
from robot_service.worker.environment import EnvironmentRuntime
from robot_service.worker.queries import build_action_apis_payload, build_robot_status
from robot_service.worker.task_runner import TaskRunner


def test_environment_runtime_tracks_environment_id_and_default_assets():
    runtime = EnvironmentRuntime()

    runtime.load_environment("env-default")

    assert runtime.current_environment_id == "env-default"
    assert runtime.scene_assets == ["ground", "light", "block"]
    assert runtime.world is None


def test_environment_runtime_uses_isaac_loader_when_simulation_app_is_present(monkeypatch):
    runtime = EnvironmentRuntime(simulation_app=object())

    def fake_load_isaac_scene(environment_id: str) -> None:
        assert environment_id == "env-default"
        runtime.scene_assets = ["ground", "light", "block"]
        runtime.world = object()

    monkeypatch.setattr(runtime, "_load_isaac_scene", fake_load_isaac_scene)

    runtime.load_environment("env-default")

    assert runtime.current_environment_id == "env-default"
    assert runtime.scene_assets == ["ground", "light", "block"]
    assert runtime.world is not None


def test_query_builders_return_placeholder_robot_and_action_api_data():
    runtime = EnvironmentRuntime()
    runtime.load_environment("env-default")

    robot_status = build_robot_status("sess-demo", runtime)
    action_apis = build_action_apis_payload("sess-demo", runtime)

    assert robot_status.robot_status == "ready"
    assert action_apis.action_apis == ["robot.pick_and_place(pick_position, place_position, rotation=None)"]


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
