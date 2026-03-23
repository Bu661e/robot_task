from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from modules.robot_bridge import (
    capture_frame,
    close_worker,
    start_worker,
)
from modules.schemas import FramePacket, ParsedTask, PointMapPacket, TaskRequest
from modules.task_parser import parse_task
from utils.task_loader import (
    load_task_request,
)


def parse_cli_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="机器人任务主流程入口")

    task_input_group = parser.add_mutually_exclusive_group(required=True)
    task_input_group.add_argument(
        "--instruction",
        type=str,
        help="手动输入任务指令文本",
    )
    task_input_group.add_argument(
        "--task-file",
        type=Path,
        help="从任务文件(yaml)读取任务",
    )
    parser.add_argument(
        "--task-index",
        type=int,
        help="任务文件中的任务序号，从 1 开始",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("res"),
        help="输出目录，默认写入 res/",
    )
    parser.add_argument(
        "--scene-id",
        type=str,
        default="default_scene",
        help="robot worker 启动时使用的桌面场景标识",
    )
    parser.add_argument(
        "--enable-robot-worker",
        action="store_true",
        help="启用 robot worker 骨架流程。默认关闭，便于在非 Isaac 环境下继续开发主进程。",
    )
    parser.add_argument(
        "--robot-headless",
        action="store_true",
        help="启用 robot worker 时，以 headless 模式启动 Isaac Sim。",
    )
    args = parser.parse_args(argv)

    if args.task_file is not None and args.task_index is None:
        parser.error("使用 --task-file 时必须同时提供 --task-index")
    if args.instruction is not None and args.task_index is not None:
        parser.error("使用 --instruction 时不需要提供 --task-index")
    if args.task_index is not None and args.task_index < 1:
        parser.error("--task-index 必须大于等于 1")
    return args


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_cli_args(argv)
    output_dir = _build_run_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    task: TaskRequest = load_task_request(args)
    parsed_task: ParsedTask = parse_task(task)

    _write_json(output_dir / "task_request.json", task)
    _write_json(output_dir / "parsed_task.json", parsed_task)

    if args.enable_robot_worker:
        try:
            start_worker(
                scene_id=args.scene_id,
                session_dir=output_dir,
                headless=args.robot_headless,
            )
            frame_packet: FramePacket
            point_map_packet: PointMapPacket
            frame_packet, point_map_packet = capture_frame()
            _write_json(output_dir / "frame_packet.json", frame_packet)
            _write_json(output_dir / "point_map_packet.json", point_map_packet)
        finally:
            close_worker()

    print(f"加载到的任务: {task}")
    print(f"task_parser 输出: {parsed_task}")
    print(f"结果已写入: {output_dir}")
    if args.enable_robot_worker:
        print(
            "当前主流程已执行到 M2 robot_bridge 的 worker 启动与采帧请求，"
            "后续模块待实现。"
        )
    else:
        print(
            "当前主流程已执行到 M1 task_parser。robot worker 骨架已接入，"
            "如需进入 M2 请加 --enable-robot-worker。"
        )


def _build_run_output_dir(base_output_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y-%m%d-%H%M%S")
    return base_output_dir / timestamp


def _write_json(path: Path, data: object) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
