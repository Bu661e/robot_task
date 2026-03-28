from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from robot_service.common.messages import WorkerCommand, WorkerEvent
from robot_service.common.schemas import CreateTaskRequest
from robot_service.runtime.logging_config import configure_logging
from robot_service.worker.environment import EnvironmentRuntime
from robot_service.worker.queries import (
    build_action_apis_payload,
    build_cameras_payload,
    build_robot_status,
)
from robot_service.worker.task_runner import TaskRunner


def _bootstrap_simulation_app(logger):
    try:
        from isaacsim import SimulationApp
    except ImportError:
        logger.warning("Isaac Sim Python modules are unavailable. Worker will run in placeholder mode.")
        return None

    return SimulationApp({"headless": True})


def _emit(event: WorkerEvent) -> None:
    sys.stdout.write(event.model_dump_json() + "\n")
    sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--session-dir", required=True)
    args = parser.parse_args()

    session_dir = Path(args.session_dir)
    logger = configure_logging(log_file=session_dir / "run.log")
    simulation_app = _bootstrap_simulation_app(logger)
    runtime = EnvironmentRuntime(session_dir=session_dir, simulation_app=simulation_app)
    task_runner = TaskRunner(runtime)

    # Isaac Sim launched via python.sh may defer text-stdin iteration until EOF.
    # Read from the binary buffer directly so line-based commands can be processed
    # while stdin remains open for later requests.
    stdin_buffer = getattr(sys.stdin, "buffer", None)
    while True:
        if stdin_buffer is not None:
            raw_bytes = stdin_buffer.readline()
            if not raw_bytes:
                break
            raw_line = raw_bytes.decode("utf-8", errors="replace")
        else:
            raw_line = sys.stdin.readline()
            if not raw_line:
                break

        if not raw_line.strip():
            continue
        command = WorkerCommand.model_validate(json.loads(raw_line))
        if command.command_type == "load_environment":
            runtime.load_environment(command.payload["environment_id"])
            _emit(
                WorkerEvent(
                    request_id=command.request_id,
                    event_type="environment_loaded",
                    payload={"environment_id": runtime.current_environment_id},
                )
            )
            continue

        if command.command_type == "get_robot_status":
            response = build_robot_status(args.session_id, runtime)
            _emit(
                WorkerEvent(
                    request_id=command.request_id,
                    event_type="robot_status",
                    payload=response.model_dump(exclude={"session_id"}, mode="json"),
                )
            )
            continue

        if command.command_type == "get_cameras":
            response, artifact_records = build_cameras_payload(args.session_id, runtime)
            payload = response.model_dump(exclude={"session_id"}, mode="json")
            if artifact_records:
                payload["artifact_records"] = [artifact.model_dump(mode="json") for artifact in artifact_records]
            _emit(
                WorkerEvent(
                    request_id=command.request_id,
                    event_type="cameras_payload",
                    payload=payload,
                )
            )
            continue

        if command.command_type == "get_action_apis":
            response = build_action_apis_payload(args.session_id, runtime)
            _emit(
                WorkerEvent(
                    request_id=command.request_id,
                    event_type="action_apis_payload",
                    payload=response.model_dump(exclude={"session_id"}, mode="json"),
                )
            )
            continue

        if command.command_type == "run_task":
            request = CreateTaskRequest.model_validate(
                {
                    "task": command.payload["task"],
                    "policy_source": command.payload["policy_source"],
                    "perception_data": command.payload["perception_data"],
                    "ext": command.payload.get("ext", {}),
                }
            )
            _emit(
                task_runner.run_task(
                    session_id=args.session_id,
                    session_task_id=command.payload["session_task_id"],
                    request=request,
                    request_id=command.request_id,
                )
            )
            continue

        if command.command_type == "cancel_task":
            _emit(task_runner.cancel_current_task(request_id=command.request_id))
            continue

        if command.command_type == "shutdown":
            _emit(
                WorkerEvent(
                    request_id=command.request_id,
                    event_type="worker_ready",
                    payload={"status": "shutting_down"},
                )
            )
            break

        _emit(
            WorkerEvent(
                request_id=command.request_id,
                event_type="worker_error",
                payload={"error_message": f"Unknown command: {command.command_type}"},
            )
        )

    if simulation_app is not None:
        simulation_app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
