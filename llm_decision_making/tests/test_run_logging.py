from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from utils.run_logging import clear_active_run_logger, start_run_logging


def test_start_run_logging_creates_expected_run_directories(tmp_path: Path) -> None:
    run_logger = start_run_logging(
        task_id="1",
        base_dir=tmp_path,
        started_at=datetime(2026, 3, 28, 16, 30, 45),
    )

    assert run_logger.root_dir == tmp_path / "2026-03-28_16-30-45_task-1"
    assert run_logger.run_log_path == run_logger.root_dir / "run.log"
    assert run_logger.run_log_path.is_file()
    assert (run_logger.root_dir / "robot_service" / "requests").is_dir()
    assert (run_logger.root_dir / "robot_service" / "responses").is_dir()
    assert (run_logger.root_dir / "robot_service" / "artifacts").is_dir()
    assert (run_logger.root_dir / "perception_service" / "requests").is_dir()
    assert (run_logger.root_dir / "perception_service" / "responses").is_dir()
    assert (run_logger.root_dir / "perception_service" / "artifacts").is_dir()

    clear_active_run_logger()


def test_run_logger_writes_console_summary_and_full_file_log(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_logger = start_run_logging(
        task_id="1",
        base_dir=tmp_path,
        started_at=datetime(2026, 3, 28, 16, 30, 45),
    )

    run_logger.log_data_flow(
        module="main",
        event="task_loaded",
        payload={"task_id": "1", "instruction": "Pick up the bottle."},
        summary="task_id=1",
    )

    captured = capsys.readouterr()

    assert "task_loaded" in captured.err
    assert "task_id=1" in captured.err
    assert "Pick up the bottle." not in captured.err

    log_text = run_logger.run_log_path.read_text(encoding="utf-8")
    assert "task_loaded" in log_text
    assert '"instruction": "Pick up the bottle."' in log_text

    clear_active_run_logger()


def test_service_logger_persists_full_http_request_and_response(
    tmp_path: Path,
) -> None:
    run_logger = start_run_logging(
        task_id="1",
        base_dir=tmp_path,
        started_at=datetime(2026, 3, 28, 16, 30, 45),
    )
    robot_logger = run_logger.service("robot_service")

    request_id = robot_logger.log_http_request(
        method="POST",
        path="/sessions",
        body={"backend_type": "isaac_sim", "environment_id": "env-default", "ext": {}},
    )
    robot_logger.log_http_response(
        request_id=request_id,
        method="POST",
        path="/sessions",
        status_code=200,
        body={
            "session_id": "sess_1",
            "session_status": "ready",
            "backend_type": "isaac_sim",
            "environment_id": "env-default",
            "ext": {},
        },
    )

    request_files = sorted((run_logger.root_dir / "robot_service" / "requests").glob("*.json"))
    response_files = sorted((run_logger.root_dir / "robot_service" / "responses").glob("*.json"))

    assert len(request_files) == 1
    assert len(response_files) == 1
    assert json.loads(request_files[0].read_text(encoding="utf-8"))["body"] == {
        "backend_type": "isaac_sim",
        "environment_id": "env-default",
        "ext": {},
    }
    assert json.loads(response_files[0].read_text(encoding="utf-8"))["body"]["session_id"] == "sess_1"

    log_text = run_logger.run_log_path.read_text(encoding="utf-8")
    assert '"backend_type": "isaac_sim"' in log_text
    assert '"session_id": "sess_1"' in log_text

    clear_active_run_logger()


def test_service_logger_saves_binary_artifact_and_logs_path_and_size(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_logger = start_run_logging(
        task_id="1",
        base_dir=tmp_path,
        started_at=datetime(2026, 3, 28, 16, 30, 45),
    )
    robot_logger = run_logger.service("robot_service")

    artifact_path = robot_logger.save_binary_artifact(
        filename="front_rgb.png",
        content=b"png-bytes",
    )

    captured = capsys.readouterr()
    log_text = run_logger.run_log_path.read_text(encoding="utf-8")

    assert artifact_path == run_logger.root_dir / "robot_service" / "artifacts" / "front_rgb.png"
    assert artifact_path.read_bytes() == b"png-bytes"
    assert "front_rgb.png" in captured.err
    assert "size_bytes=9" in captured.err
    assert "png-bytes" not in captured.err
    assert "front_rgb.png" in log_text
    assert "size_bytes=9" in log_text
    assert "png-bytes" not in log_text

    clear_active_run_logger()
