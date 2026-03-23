from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast

from robot.runtime import RobotWorkerRuntime


class RobotWorkerHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True
    block_on_close = False

    def __init__(self, server_address: tuple[str, int], runtime: RobotWorkerRuntime):
        super().__init__(server_address, RobotWorkerRequestHandler)
        self.runtime = runtime

    def request_shutdown(self) -> None:
        shutdown_thread = threading.Thread(target=self.shutdown, daemon=True)
        shutdown_thread.start()


class RobotWorkerRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self._write_json(404, {"success": False, "error": "unknown path"})
            return

        runtime = self._get_runtime()
        self._write_json(200, runtime.build_health_payload())

    def do_POST(self) -> None:  # noqa: N802
        runtime = self._get_runtime()
        request_payload = self._read_json_body()

        try:
            if self.path == "/capture_frame":
                frame_packet, point_map_packet = runtime.capture_frame()
                response_payload = {
                    "success": True,
                    "frame_packet": frame_packet,
                    "point_map_packet": point_map_packet,
                }
                self._write_json(200, response_payload)
                return

            if self.path == "/pick_and_place":
                pick_position = request_payload.get("pick_position")
                place_position = request_payload.get("place_position")
                rotation = request_payload.get("rotation")
                response_payload = runtime.pick_and_place(
                    pick_position=cast(list[float], pick_position),
                    place_position=cast(list[float], place_position),
                    rotation=cast(list[float] | None, rotation),
                )
                self._write_json(200, response_payload)
                return

            if self.path == "/reset":
                response_payload = runtime.reset()
                self._write_json(200, response_payload)
                return

            if self.path == "/shutdown":
                response_payload = runtime.shutdown()
                self._write_json(200, response_payload)
                cast(RobotWorkerHTTPServer, self.server).request_shutdown()
                return

            self._write_json(404, {"success": False, "error": "unknown path"})
        except Exception as exc:
            self._write_json(
                500,
                {
                    "success": False,
                    "error": str(exc),
                },
            )

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length == 0:
            return {}

        raw_body = self.rfile.read(content_length).decode("utf-8")
        body_payload = json.loads(raw_body)
        if not isinstance(body_payload, dict):
            raise ValueError("请求体必须是 JSON 对象。")
        return body_payload

    def _write_json(self, status_code: int, payload: dict[str, object]) -> None:
        response_text = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_text)))
        self.end_headers()
        self.wfile.write(response_text)

    def _get_runtime(self) -> RobotWorkerRuntime:
        server = cast(RobotWorkerHTTPServer, self.server)
        return server.runtime
