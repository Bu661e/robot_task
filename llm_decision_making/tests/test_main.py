from __future__ import annotations

import importlib
import inspect
import runpy
import sys
from pathlib import Path
from typing import Sequence, get_type_hints

import pytest

from modules.schemas import ParsedTask, SourceTask
from main import load_task_from_cli, run
from utils.run_logging import clear_active_run_logger, get_active_run_logger, start_run_logging
from utils.robot_schemas import SessionInfo


def test_load_task_from_cli_uses_default_task_file_and_default_objects_env_id() -> None:
    task, objects_env_id = load_task_from_cli(["--task-id", "2"])

    assert task == SourceTask(task_id="2", instruction="Pick up the smallest ball.")
    assert objects_env_id == "env-default"


def test_load_task_from_cli_accepts_custom_task_file(tmp_path: Path) -> None:
    task_file = tmp_path / "tasks.yaml"
    task_file.write_text(
        '\n'.join(
            [
                '- task_id: "10"',
                '  instruction: "Pick up the red cube."',
            ]
        ),
        encoding="utf-8",
    )

    task, objects_env_id = load_task_from_cli(
        [
            "--task-file",
            str(task_file),
            "--task-id",
            "10",
            "--objects-env-id",
            "custom-env",
        ]
    )

    assert task == SourceTask(task_id="10", instruction="Pick up the red cube.")
    assert objects_env_id == "custom-env"


def test_load_task_from_cli_uses_default_objects_env_id_when_not_provided() -> None:
    task, objects_env_id = load_task_from_cli(["--task-id", "2"])

    assert task.task_id == "2"
    assert objects_env_id == "env-default"


def test_load_task_from_cli_rejects_blank_objects_env_id() -> None:
    with pytest.raises(ValueError, match="objects_env_id must not be empty"):
        load_task_from_cli(["--task-id", "2", "--objects-env-id", "   "])


def test_run_returns_parsed_task_and_calls_robot_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = SourceTask(task_id="manual", instruction="Do not load from CLI.")
    session = SessionInfo(
        session_id="sess_1",
        session_status="ready",
        backend_type="isaac_sim",
        environment_id="env-default",
        ext={},
    )
    call_order: list[tuple[str, str]] = []

    class FakeTaskParser:
        @classmethod
        def from_config(cls) -> FakeTaskParser:
            return cls()

        def parse_task(self, task_description: SourceTask) -> ParsedTask:
            return ParsedTask(
                task_id=task_description.task_id,
                instruction=task_description.instruction,
                object_texts=["bottle"],
            )

    monkeypatch.setattr("main.TaskParser", FakeTaskParser)
    
    class FakeRobotClient:
        def get_robot(self, session_id: str) -> object:
            call_order.append(("get_robot", session_id))
            return object()

        def get_cameras(self, session_id: str) -> object:
            call_order.append(("get_cameras", session_id))
            return object()

        def close_session(self, session_id: str) -> object:
            call_order.append(("close_session", session_id))
            return object()

    monkeypatch.setattr("main.default_robot_client", FakeRobotClient())

    assert run(task, session) is None
    assert call_order == [
        ("get_robot", "sess_1"),
        ("get_cameras", "sess_1"),
        ("close_session", "sess_1"),
    ]


def test_run_signature_uses_fixed_task_and_session_types() -> None:
    signature = inspect.signature(run)
    task_parameter = signature.parameters["task"]
    session_parameter = signature.parameters["session"]

    assert task_parameter.default is inspect.Signature.empty
    assert session_parameter.default is inspect.Signature.empty
    assert get_type_hints(run)["task"] is SourceTask
    assert get_type_hints(run)["session"] is SessionInfo
    assert get_type_hints(run)["return"] is type(None)


def test_load_task_from_cli_signature_uses_fixed_argv_type() -> None:
    argv_parameter = inspect.signature(load_task_from_cli).parameters["argv"]

    assert argv_parameter.default is inspect.Signature.empty
    assert get_type_hints(load_task_from_cli)["argv"] == Sequence[str]
    assert get_type_hints(load_task_from_cli)["return"] == tuple[SourceTask, str]


def test_default_task_file_is_defined_in_main_config() -> None:
    main_config = importlib.import_module("config.main_config")

    assert main_config.DEFAULT_TASK_FILE == (
        Path(__file__).resolve().parent.parent / "tasks" / "tasks_en.yaml"
    )


def test_main_does_not_expose_helper_functions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main_module = importlib.import_module("main")

    assert not hasattr(main_module, "_normalize_objects_env_id")
    assert not hasattr(main_module, "create_robot_client")


def test_run_closes_session_when_task_parser_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = SourceTask(task_id="manual", instruction="Pick up the bottle.")
    session = SessionInfo(
        session_id="sess_1",
        session_status="ready",
        backend_type="isaac_sim",
        environment_id="env-default",
        ext={},
    )
    call_order: list[tuple[str, str]] = []

    class FakeTaskParser:
        @classmethod
        def from_config(cls) -> FakeTaskParser:
            return cls()

        def parse_task(self, task_description: SourceTask) -> ParsedTask:
            raise RuntimeError("parse failed")

    monkeypatch.setattr("main.TaskParser", FakeTaskParser)

    class FakeRobotClient:
        def get_robot(self, session_id: str) -> object:
            call_order.append(("get_robot", session_id))
            return object()

        def get_cameras(self, session_id: str) -> object:
            call_order.append(("get_cameras", session_id))
            return object()

        def close_session(self, session_id: str) -> object:
            call_order.append(("close_session", session_id))
            return object()

    monkeypatch.setattr("main.default_robot_client", FakeRobotClient())

    with pytest.raises(RuntimeError, match="parse failed"):
        run(task, session)

    assert call_order == [
        ("close_session", "sess_1"),
    ]


def test_run_logs_task_input_and_parsed_output_when_run_logger_is_active(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    task = SourceTask(task_id="manual", instruction="Pick up the bottle.")
    session = SessionInfo(
        session_id="sess_1",
        session_status="ready",
        backend_type="isaac_sim",
        environment_id="env-default",
        ext={},
    )
    run_logger = start_run_logging(task_id=task.task_id, base_dir=tmp_path)

    class FakeTaskParser:
        @classmethod
        def from_config(cls) -> FakeTaskParser:
            return cls()

        def parse_task(self, task_description: SourceTask) -> ParsedTask:
            return ParsedTask(
                task_id=task_description.task_id,
                instruction=task_description.instruction,
                object_texts=["bottle"],
            )

    monkeypatch.setattr("main.TaskParser", FakeTaskParser)

    class FakeRobotClient:
        def get_robot(self, session_id: str) -> object:
            return object()

        def get_cameras(self, session_id: str) -> object:
            return object()

        def close_session(self, session_id: str) -> object:
            return object()

    monkeypatch.setattr("main.default_robot_client", FakeRobotClient())

    run(task, session)

    log_text = run_logger.run_log_path.read_text(encoding="utf-8")
    assert '"instruction": "Pick up the bottle."' in log_text
    assert '"object_texts": [' in log_text

    clear_active_run_logger()


def test_main_cli_creates_and_clears_run_logger(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    task = SourceTask(task_id="manual", instruction="Pick up the bottle.")

    class FakeTaskParser:
        @classmethod
        def from_config(cls) -> FakeTaskParser:
            return cls()

        def parse_task(self, task_description: SourceTask) -> ParsedTask:
            return ParsedTask(
                task_id=task_description.task_id,
                instruction=task_description.instruction,
                object_texts=["bottle"],
            )

    class FakeRobotClient:
        def create_session(self, environment_id: str) -> SessionInfo:
            return SessionInfo(
                session_id="sess_1",
                session_status="ready",
                backend_type="isaac_sim",
                environment_id=environment_id,
                ext={},
            )

        def get_robot(self, session_id: str) -> object:
            return object()

        def get_cameras(self, session_id: str) -> object:
            return object()

        def close_session(self, session_id: str) -> object:
            return object()

    monkeypatch.setattr("modules.task_loader.TaskLoader.load_from_cli", lambda self, task_file, task_id: task)
    monkeypatch.setattr("modules.task_parser.TaskParser", FakeTaskParser)
    monkeypatch.setattr("utils.robot_client.default_robot_client", FakeRobotClient())
    monkeypatch.setattr("utils.run_logging.RUNS_DIR", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "--task-id", task.task_id],
    )

    runpy.run_module("main", run_name="__main__")

    run_directories = sorted(tmp_path.glob("*_task-manual"))
    assert len(run_directories) == 1
    assert get_active_run_logger() is None
    log_text = (run_directories[0] / "run.log").read_text(encoding="utf-8")
    assert '"instruction": "Pick up the bottle."' in log_text
    assert '"object_texts": [' in log_text
