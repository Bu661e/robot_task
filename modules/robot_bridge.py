from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO, cast
from urllib import error, request

from .schemas import FramePacket, PointMapPacket

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8899
_DEFAULT_READY_TIMEOUT_S = 30.0
_DEFAULT_HTTP_TIMEOUT_S = 5.0
_DEFAULT_POLL_INTERVAL_S = 0.5


@dataclass
class _WorkerContext:
    process: subprocess.Popen[str]
    base_url: str
    scene_id: str
    session_dir: Path
    stdout_handle: TextIO
    stderr_handle: TextIO


class RobotProxy:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    def pick_and_place(
        self,
        pick_position: list[float],
        place_position: list[float],
        rotation: list[float] | None = None,
    ) -> dict[str, object]:
        payload = {
            "pick_position": pick_position,
            "place_position": place_position,
            "rotation": rotation,
        }
        return _request_json(
            method="POST",
            url=f"{self._base_url}/pick_and_place",
            payload=payload,
        )


_WORKER_CONTEXT: _WorkerContext | None = None


def start_worker(scene_id: str, session_dir: Path, headless: bool = False) -> None:
    global _WORKER_CONTEXT
    if _WORKER_CONTEXT is not None:
        raise RuntimeError("robot worker 已经启动，请先关闭当前 worker。")

    session_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = session_dir / "robot_worker.stdout.log"
    stderr_path = session_dir / "robot_worker.stderr.log"
    stdout_handle = stdout_path.open("w", encoding="utf-8")
    stderr_handle = stderr_path.open("w", encoding="utf-8")

    autorun_path = _get_repo_root() / "robot" / "autorun.sh"
    command = [
        str(autorun_path),
        "--host",
        _DEFAULT_HOST,
        "--port",
        str(_DEFAULT_PORT),
        "--scene-id",
        scene_id,
        "--session-dir",
        str(session_dir),
        "--headless",
        "1" if headless else "0",
    ]

    try:
        process = subprocess.Popen(
            command,
            cwd=_get_repo_root(),
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
        )
    except Exception:
        stdout_handle.close()
        stderr_handle.close()
        raise
    base_url = f"http://{_DEFAULT_HOST}:{_DEFAULT_PORT}"
    _WORKER_CONTEXT = _WorkerContext(
        process=process,
        base_url=base_url,
        scene_id=scene_id,
        session_dir=session_dir,
        stdout_handle=stdout_handle,
        stderr_handle=stderr_handle,
    )

    try:
        _wait_until_ready(_WORKER_CONTEXT)
    except Exception:
        close_worker(force=True)
        raise


def capture_frame() -> tuple[FramePacket, PointMapPacket]:
    context = _require_worker_context()
    response_payload = _request_json(
        method="POST",
        url=f"{context.base_url}/capture_frame",
        payload={},
    )

    frame_packet_raw = response_payload.get("frame_packet")
    point_map_packet_raw = response_payload.get("point_map_packet")
    if not isinstance(frame_packet_raw, dict):
        raise ValueError("worker 返回缺少 frame_packet。")
    if not isinstance(point_map_packet_raw, dict):
        raise ValueError("worker 返回缺少 point_map_packet。")

    frame_packet: FramePacket = cast(FramePacket, frame_packet_raw)
    point_map_packet: PointMapPacket = cast(PointMapPacket, point_map_packet_raw)
    return frame_packet, point_map_packet


def get_robot() -> RobotProxy:
    context = _require_worker_context()
    return RobotProxy(base_url=context.base_url)


def reset_worker() -> None:
    context = _require_worker_context()
    _request_json(
        method="POST",
        url=f"{context.base_url}/reset",
        payload={},
    )


def close_worker(force: bool = False) -> None:
    global _WORKER_CONTEXT
    context = _WORKER_CONTEXT
    if context is None:
        return

    try:
        if not force and context.process.poll() is None:
            try:
                _request_json(
                    method="POST",
                    url=f"{context.base_url}/shutdown",
                    payload={},
                    timeout_s=2.0,
                )
            except Exception:
                pass

        if context.process.poll() is None:
            try:
                context.process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                context.process.kill()
                context.process.wait(timeout=5.0)
    finally:
        context.stdout_handle.close()
        context.stderr_handle.close()
        _WORKER_CONTEXT = None


def _wait_until_ready(context: _WorkerContext) -> None:
    deadline = time.monotonic() + _DEFAULT_READY_TIMEOUT_S
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        if context.process.poll() is not None:
            raise RuntimeError(
                "robot worker 在就绪前退出。请查看 robot_worker.stdout.log 和 "
                "robot_worker.stderr.log。"
            )

        try:
            health_payload = _request_json(
                method="GET",
                url=f"{context.base_url}/health",
                timeout_s=2.0,
            )
            if bool(health_payload.get("ready")):
                return
        except Exception as exc:
            last_error = exc

        time.sleep(_DEFAULT_POLL_INTERVAL_S)

    if last_error is None:
        raise TimeoutError("等待 robot worker 就绪超时。")
    raise TimeoutError(f"等待 robot worker 就绪超时，最后一次错误: {last_error}")


def _request_json(
    method: str,
    url: str,
    payload: dict[str, object] | None = None,
    timeout_s: float = _DEFAULT_HTTP_TIMEOUT_S,
) -> dict[str, Any]:
    body: bytes | None = None
    headers = {
        "Content-Type": "application/json",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    http_request = request.Request(
        url=url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with request.urlopen(http_request, timeout=timeout_s) as response:
            response_text = response.read().decode("utf-8")
    except error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"robot worker HTTP {exc.code}: {error_text}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"robot worker 连接失败: {exc}") from exc

    response_payload = json.loads(response_text)
    if not isinstance(response_payload, dict):
        raise ValueError("robot worker 响应必须是 JSON 对象。")
    return response_payload


def _require_worker_context() -> _WorkerContext:
    if _WORKER_CONTEXT is None:
        raise RuntimeError("robot worker 尚未启动。")
    return _WORKER_CONTEXT


def _get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent
