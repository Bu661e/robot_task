from __future__ import annotations

import argparse
from pathlib import Path
import sys
import threading

from robot.runtime import RobotWorkerRuntime
from robot.server import RobotWorkerHTTPServer


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
    server: RobotWorkerHTTPServer | None = None
    server_thread: threading.Thread | None = None

    try:
        server = _create_http_server(
            host=args.host,
            port=args.port,
            runtime=runtime,
        )
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        runtime.initialize_best_effort()
        if runtime.last_error is not None:
            print(
                "robot worker 初始化失败，可用 "
                f"`curl http://{args.host}:{args.port}/health` 查看详细错误："
                f"{runtime.last_error}",
                file=sys.stderr,
                flush=True,
            )

        runtime.run_forever()
    except KeyboardInterrupt:
        runtime.shutdown()
    finally:
        if server is not None and server_thread is not None:
            _stop_http_server(server=server, server_thread=server_thread)
        runtime.close()


def _parse_headless_flag(raw_value: str) -> bool:
    return raw_value == "1"


def _create_http_server(host: str, port: int, runtime: RobotWorkerRuntime) -> RobotWorkerHTTPServer:
    try:
        return RobotWorkerHTTPServer(
            server_address=(host, port),
            runtime=runtime,
        )
    except OSError as exc:
        print(
            _build_port_in_use_message(host=host, port=port, error_message=str(exc)),
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(1) from exc


def _stop_http_server(server: RobotWorkerHTTPServer, server_thread: threading.Thread) -> None:
    server.request_shutdown()
    server_thread.join(timeout=5.0)
    server.server_close()


def _build_port_in_use_message(host: str, port: int, error_message: str) -> str:
    return (
        f"robot worker 无法绑定 {host}:{port}：{error_message}\n"
        "这通常表示已有旧的 robot worker 仍在运行。\n"
        f"可先检查：curl -s http://{host}:{port}/health\n"
        f"如需关闭旧 worker：curl -X POST http://{host}:{port}/shutdown\n"
        f"若端口被其他程序占用，可用 `ss -ltnp | rg ':{port}\\b'` 排查。"
    )


if __name__ == "__main__":
    main()
