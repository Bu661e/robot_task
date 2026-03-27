from pathlib import Path

from robot_service.runtime.ids import new_artifact_id, new_session_id, new_session_task_id
from robot_service.runtime.paths import get_artifact_path, get_runs_dir, get_session_run_dir
from robot_service.runtime.settings import Settings


def test_settings_reads_environment_variables(monkeypatch):
    monkeypatch.setenv("ROBOT_SERVICE_HOST", "0.0.0.0")
    monkeypatch.setenv("ROBOT_SERVICE_PORT", "9000")
    monkeypatch.setenv("ISAAC_SIM_ROOT", "/opt/isaacsim")
    monkeypatch.setenv("RUNS_DIR", "/tmp/robot-runs")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings.from_env()

    assert settings.robot_service_host == "0.0.0.0"
    assert settings.robot_service_port == 9000
    assert settings.isaac_sim_root == "/opt/isaacsim"
    assert settings.runs_dir == Path("/tmp/robot-runs")
    assert settings.log_level == "DEBUG"


def test_id_builders_include_expected_prefixes():
    session_id = new_session_id("isaac_sim")
    task_id = new_session_task_id()
    artifact_id = new_artifact_id("rgb", session_id)

    assert session_id.startswith("sess_isaac_sim_")
    assert task_id.startswith("task_")
    assert artifact_id.startswith(f"artifact_rgb_{session_id}_")


def test_path_helpers_build_paths_under_runs_dir(tmp_path):
    runs_dir = get_runs_dir(tmp_path / "runs")
    session_id = "sess_isaac_sim_20260328120000_abcd"
    artifact_id = "artifact_rgb_sess_isaac_sim_20260328120000_abcd_0001"

    session_dir = get_session_run_dir(runs_dir, session_id)
    artifact_path = get_artifact_path(session_dir, artifact_id, ".png")

    assert session_dir == runs_dir / session_id
    assert artifact_path == session_dir / "artifacts" / f"{artifact_id}.png"

