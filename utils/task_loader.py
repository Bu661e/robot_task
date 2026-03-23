from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.schemas import TaskRequest
else:
    TaskRequest = dict[str, str]


def _build_manual_task(instruction: str) -> TaskRequest:
    return {
        "task_id": "manual",
        "instruction": instruction,
    }


def _load_yaml_tasks(task_file: Path) -> list[dict[str, object]]:
    tasks: list[dict[str, object]] = []
    current_task: dict[str, object] | None = None

    for raw_line in task_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("- "):
            if current_task is not None:
                tasks.append(current_task)
            current_task = {}
            line = line[2:].strip()
            if not line:
                continue

        if current_task is None:
            raise ValueError("yaml 任务文件格式错误")

        if ":" not in line:
            raise ValueError(f"无法解析的 yaml 行: {raw_line}")

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if value.startswith('"') and value.endswith('"'):
            parsed_value: object = value[1:-1]
        elif value.isdigit():
            parsed_value = int(value)
        else:
            parsed_value = value
        current_task[key] = parsed_value

    if current_task is not None:
        tasks.append(current_task)
    return tasks


def _load_json_tasks(task_file: Path) -> list[dict[str, object]]:
    data = json.loads(task_file.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("任务文件内容必须是 list")
    if any(not isinstance(item, dict) for item in data):
        raise ValueError("任务文件中的每一项都必须是 dict")
    return data


def _load_tasks(task_file: Path) -> list[dict[str, object]]:
    suffix = task_file.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return _load_yaml_tasks(task_file)
    if suffix == ".json":
        return _load_json_tasks(task_file)
    raise ValueError(f"不支持的任务文件格式: {task_file}")


def build_task_request_from_instruction(instruction: str) -> TaskRequest:
    return _build_manual_task(instruction)


def build_task_request_from_file(task_file: Path, task_index: int) -> TaskRequest:
    tasks = _load_tasks(task_file)
    if task_index > len(tasks):
        raise IndexError(f"任务序号超出范围: {task_index}, 总任务数: {len(tasks)}")

    task_data = tasks[task_index - 1]
    task_id = task_data.get("task_id")
    instruction = task_data.get("instruction")
    if task_id is None or instruction is None:
        raise ValueError("任务项必须包含 task_id 和 instruction")
    if not isinstance(instruction, str):
        raise TypeError("instruction 必须是 str")
    return {
        "task_id": str(task_id),
        "instruction": instruction,
    }


def load_task_request(args: argparse.Namespace) -> TaskRequest:
    if args.instruction is not None:
        return build_task_request_from_instruction(args.instruction)
    return build_task_request_from_file(args.task_file, args.task_index)
