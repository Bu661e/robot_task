from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from config.main_config import DEFAULT_OBJECTS_ENV_ID, DEFAULT_TASK_FILE
from modules.schemas import ParsedTask, SourceTask
from modules.task_parser import TaskParser
from modules.task_loader import TaskLoader
from utils.robot_client import default_robot_client
from utils.run_logging import clear_active_run_logger, get_active_run_logger, start_run_logging
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
        default=DEFAULT_OBJECTS_ENV_ID,
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
        run_logger = get_active_run_logger()
        if run_logger is not None:
            run_logger.log_data_flow(
                module="main",
                event="task_input",
                payload=task,
                summary=f"task_id={task.task_id}",
            )
            run_logger.log_data_flow(
                module="main",
                event="session_input",
                payload=session,
                summary=f"session_id={session.session_id}",
            )

        task_parser: TaskParser = TaskParser.from_config()
        parsed_task: ParsedTask = task_parser.parse_task(task)
        if run_logger is not None:
            run_logger.log_data_flow(
                module="task_parser",
                event="task_parsed",
                payload=parsed_task,
                summary=f"task_id={parsed_task.task_id} objects={','.join(parsed_task.object_texts)}",
            )

        default_robot_client.get_robot(session.session_id)
        default_robot_client.get_cameras(session.session_id)
    finally:
        default_robot_client.close_session(session.session_id)


if __name__ == "__main__":
    task, objects_env_id = load_task_from_cli(sys.argv[1:])
    start_run_logging(task.task_id)
    try:
        run_logger = get_active_run_logger()
        if run_logger is not None:
            run_logger.log_data_flow(
                module="main",
                event="task_loaded",
                payload={
                    "task": task,
                    "objects_env_id": objects_env_id,
                },
                summary=f"task_id={task.task_id} objects_env_id={objects_env_id}",
            )

        session = default_robot_client.create_session(objects_env_id)
        run(task, session)
    finally:
        clear_active_run_logger()
