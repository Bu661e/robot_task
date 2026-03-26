from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Sequence, get_type_hints

from modules.schemas import TaskDescription
from main import load_task_from_cli, process


def test_load_task_from_cli_uses_default_task_file() -> None:
    task = load_task_from_cli(["--task-id", "2"])

    assert task == TaskDescription(
        task_id="2",
        objects_env_id="2-ycb",
        instruction="Pick up the smallest ball.",
    )


def test_load_task_from_cli_accepts_custom_task_file(tmp_path: Path) -> None:
    task_file = tmp_path / "tasks.yaml"
    task_file.write_text(
        '\n'.join(
            [
                '- task_id: "10"',
                '  objects_env_id: "custom-env"',
                '  instruction: "Pick up the red cube."',
            ]
        ),
        encoding="utf-8",
    )

    task = load_task_from_cli(["--task-file", str(task_file), "--task-id", "10"])

    assert task == TaskDescription(
        task_id="10",
        objects_env_id="custom-env",
        instruction="Pick up the red cube.",
    )


def test_process_returns_explicit_task() -> None:
    task = TaskDescription(
        task_id="manual",
        objects_env_id="env-1",
        instruction="Do not load from CLI.",
    )

    assert process(task) == task


def test_process_signature_uses_fixed_task_type() -> None:
    task_parameter = inspect.signature(process).parameters["task"]

    assert task_parameter.default is inspect.Signature.empty
    assert get_type_hints(process)["task"] is TaskDescription


def test_load_task_from_cli_signature_uses_fixed_argv_type() -> None:
    argv_parameter = inspect.signature(load_task_from_cli).parameters["argv"]

    assert argv_parameter.default is inspect.Signature.empty
    assert get_type_hints(load_task_from_cli)["argv"] == Sequence[str]


def test_default_task_file_is_defined_in_main_config() -> None:
    main_config = importlib.import_module("config.main_config")

    assert main_config.DEFAULT_TASK_FILE == (
        Path(__file__).resolve().parent.parent / "tasks" / "tasks_en.yaml"
    )
