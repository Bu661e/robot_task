from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from config.main_config import DEFAULT_TASK_FILE
from modules.schemas import ParsedTask, SourceTask
from modules.task_parser import TaskParser
from modules.task_loader import TaskLoader
from utils.robot_client import default_robot_client
from utils.robot_schemas import SessionInfo


def load_task_from_cli(argv: Sequence[str]) -> tuple[SourceTask, str]:
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
    parser.add_argument(
        "--objects-env-id",
        required=True,
        help="Environment identifier used to initialize the robot client.",
    )
    args = parser.parse_args(argv)

    task_loader = TaskLoader()
    task = task_loader.load_from_cli(task_file=args.task_file, task_id=args.task_id)
    objects_env_id = args.objects_env_id.strip()
    if not objects_env_id:
        raise ValueError("objects_env_id must not be empty.")

    return task, objects_env_id


def run(task: SourceTask, session: SessionInfo) -> None:
    try:
        task_parser: TaskParser = TaskParser.from_config()
        task_parser.parse_task(task)
        default_robot_client.get_robot(session.session_id)
        default_robot_client.get_cameras(session.session_id)
    finally:
        default_robot_client.close_session(session.session_id)


if __name__ == "__main__":
    task, objects_env_id = load_task_from_cli(sys.argv[1:])
    session = default_robot_client.create_session(objects_env_id)

    run(task, session)
