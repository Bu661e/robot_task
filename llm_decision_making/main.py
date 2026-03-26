from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from config.main_config import DEFAULT_TASK_FILE
from modules.schemas import ParsedTask, SourceTask
from modules.task_parser import TaskParser
from modules.task_loader import TaskLoader
from utils.robot_client import RobotClient


def _normalize_objects_env_id(objects_env_id: str) -> str:
    normalized_objects_env_id = objects_env_id.strip()
    if not normalized_objects_env_id:
        raise ValueError("objects_env_id must not be empty.")

    return normalized_objects_env_id


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
    objects_env_id = _normalize_objects_env_id(args.objects_env_id)
    return task, objects_env_id

# 整个llm决策流程的主函数，输入是一个SourceTask，最后会让远程执行模块执行这个任务
def process(task: SourceTask, robot_client: RobotClient) -> ParsedTask:
    task_parser: TaskParser = TaskParser.from_config()
    parsed_task: ParsedTask = task_parser.parse_task(task)
    print("Parsed Task:", parsed_task)
    return parsed_task


if __name__ == "__main__":
    new_task, objects_env_id = load_task_from_cli(sys.argv[1:])
    # TODO：使用 objects_env_id 创建 robot_client，这部分不在本次改动中实现
    robot_client = RobotClient()  # Replace with actual robot client initialization
    process(new_task, robot_client)
