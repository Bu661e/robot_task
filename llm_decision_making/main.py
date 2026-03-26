from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from config.main_config import DEFAULT_TASK_FILE
from modules.schemas import TaskDescription
from modules.task_loader import TaskLoader

def load_task_from_cli(argv: Sequence[str]) -> TaskDescription:
    parser = argparse.ArgumentParser(description="Load a task description from YAML.")
    parser.add_argument(
        "--task-file",
        type=Path,
        default=DEFAULT_TASK_FILE,
        help="Path to the YAML file that stores task definitions.",
    )
    parser.add_argument(
        "--task-id",
        required=True,
        help="Task ID to load from the YAML file.",
    )
    args = parser.parse_args(argv)

    task_loader = TaskLoader()
    return task_loader.load_from_cli(task_file=args.task_file, task_id=args.task_id)


def process(task: TaskDescription) -> TaskDescription:
    # TODO: 调用task_parser解析task
    return task


if __name__ == "__main__":
    new_task: TaskDescription = load_task_from_cli(sys.argv[1:])
    process(new_task)
