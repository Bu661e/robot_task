from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from robot_task.m1_task_parser import parse_task
from robot_task.robot_bridge import RobotBridge


TASKS_FILE = PROJECT_ROOT / "tasks" / "m1_tasks_en.json"
RES_ROOT = PROJECT_ROOT / "res"


def load_tasks(tasks_file: Path) -> list[dict]:
    return json.loads(tasks_file.read_text(encoding="utf-8"))


def build_res_dir(task_id: int | str) -> Path:
    return RES_ROOT / f"task_{task_id}"


def run_task(task_request: dict) -> dict:
    res_dir = build_res_dir(task_request["task_id"])
    res_dir.mkdir(parents=True, exist_ok=True)

    parsed_task = parse_task(task_request=task_request, res_dir=str(res_dir))

    # Future modules will be added here in pipeline order.
    # robot_bridge: RobotBridge = ...
    # frame_packet, point_map_packet, robot = robot_bridge.capture_frame()
    # robot_context = ...
    # camera_perception = ...
    # world_perception = ...
    # policy_code = ...
    # execution_result = ...

    return {
        "task_id": task_request["task_id"],
        "parsed_task": parsed_task,
        "res_dir": str(res_dir),
    }


def main() -> None:
    tasks = load_tasks(TASKS_FILE)
    results = []

    for task_request in tasks:
        result = run_task(task_request)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False))

    summary_path = RES_ROOT / "summary.json"
    RES_ROOT.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
