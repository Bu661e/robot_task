from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Sequence, get_type_hints

import pytest

from modules.schemas import ParsedTask, SourceTask
from main import create_robot_client, load_task_from_cli, process


def test_load_task_from_cli_uses_default_task_file() -> None:
    task, objects_env_id = load_task_from_cli(
        ["--task-id", "2", "--objects-env-id", "2-ycb"]
    )

    assert task == SourceTask(task_id="2", instruction="Pick up the smallest ball.")
    assert objects_env_id == "2-ycb"


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


def test_load_task_from_cli_requires_objects_env_id() -> None:
    with pytest.raises(SystemExit):
        load_task_from_cli(["--task-id", "2"])


def test_load_task_from_cli_rejects_blank_objects_env_id() -> None:
    with pytest.raises(ValueError, match="objects_env_id must not be empty"):
        load_task_from_cli(["--task-id", "2", "--objects-env-id", "   "])


def test_process_returns_parsed_task(monkeypatch: pytest.MonkeyPatch) -> None:
    task = SourceTask(task_id="manual", instruction="Do not load from CLI.")

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

    assert process(task, robot_client=object()) == ParsedTask(
        task_id="manual",
        instruction="Do not load from CLI.",
        object_texts=["bottle"],
    )


def test_process_signature_uses_fixed_task_type() -> None:
    task_parameter = inspect.signature(process).parameters["task"]

    assert task_parameter.default is inspect.Signature.empty
    assert get_type_hints(process)["task"] is SourceTask
    assert get_type_hints(process)["return"] is ParsedTask


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


def test_create_robot_client_returns_shared_default_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    monkeypatch.setattr("main.default_robot_client", sentinel)

    assert create_robot_client() is sentinel
