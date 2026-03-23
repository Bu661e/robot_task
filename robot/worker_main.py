from __future__ import annotations

import argparse
from pathlib import Path

from robot.http_server import RobotWorkerHTTPServer
from robot.runtime import RobotWorkerRuntime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Isaac Sim robot worker")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--scene-id", type=str, required=True)
    parser.add_argument("--session-dir", type=Path, required=True)
    parser.add_argument("--headless", type=_parse_headless_flag, default=False)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    runtime = RobotWorkerRuntime(
        scene_id=args.scene_id,
        session_dir=args.session_dir,
        headless=args.headless,
    )
    runtime.initialize_best_effort()

    server = RobotWorkerHTTPServer(
        server_address=(args.host, args.port),
        runtime=runtime,
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()
        runtime.close()


def _parse_headless_flag(raw_value: str) -> bool:
    return raw_value == "1"


if __name__ == "__main__":
    main()
