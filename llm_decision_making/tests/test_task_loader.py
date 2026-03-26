from __future__ import annotations

from pathlib import Path

import pytest

from modules.schemas import TaskDescription
from modules.task_loader import TaskLoader


def test_load_from_cli_reads_task_by_task_id(tmp_path: Path) -> None:
    task_file = tmp_path / "tasks.yaml"
    task_file.write_text(
        '\n'.join(
            [
                '- task_id: "1"',
                '  objects_env_id: "env-a"',
                '  instruction: "Pick up the tallest bottle."',
                '- task_id: "2"',
                '  objects_env_id: "env-b"',
                '  instruction: "Pick up the smallest ball."',
            ]
        ),
        encoding="utf-8",
    )

    task = TaskLoader().load_from_cli(task_file=task_file, task_id="2")

    assert task == TaskDescription(
        task_id="2",
        objects_env_id="env-b",
        instruction="Pick up the smallest ball.",
    )


def test_load_from_cli_raises_for_missing_task_id(tmp_path: Path) -> None:
    task_file = tmp_path / "tasks.yaml"
    task_file.write_text(
        '\n'.join(
            [
                '- task_id: "1"',
                '  objects_env_id: "env-a"',
                '  instruction: "Pick up the tallest bottle."',
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Task ID '404' not found"):
        TaskLoader().load_from_cli(task_file=task_file, task_id="404")


def test_load_from_http_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        TaskLoader().load_from_http()
