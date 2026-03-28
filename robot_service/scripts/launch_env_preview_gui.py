from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch the robot_service preview environment in Isaac Sim GUI mode."
    )
    parser.add_argument(
        "--environment-id",
        default="env-default",
        help="Environment id to load. Defaults to env-default.",
    )
    parser.add_argument(
        "--session-dir",
        default=None,
        help="Directory for runtime logs and temporary artifacts. Defaults to /tmp/robot-gui-preview-<environment>.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional frame limit for automated smoke tests. Omit for interactive preview.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session_dir = Path(args.session_dir or f"/tmp/robot-gui-preview-{args.environment_id}")
    session_dir.mkdir(parents=True, exist_ok=True)

    print("Launching Isaac Sim GUI preview")
    print(f"  repo_root: {REPO_ROOT}")
    print(f"  environment_id: {args.environment_id}")
    print(f"  session_dir: {session_dir}")
    print(f"  display: {os.environ.get('DISPLAY', '<unset>')}")

    from isaacsim import SimulationApp

    simulation_app = SimulationApp({"headless": False})
    try:
        from robot_service.worker.environment import EnvironmentRuntime

        runtime = EnvironmentRuntime(session_dir=session_dir, simulation_app=simulation_app)
        runtime.load_environment(args.environment_id)
        world = runtime.world

        print(f"GUI preview ready: {args.environment_id} loaded.")
        if args.max_frames is None:
            print("Close the Isaac Sim window when you are finished checking the scene.")
        else:
            print(f"Running for at most {args.max_frames} rendered frames.")

        frame_count = 0
        while simulation_app.is_running():
            if world is not None:
                world.step(render=True)
            else:
                simulation_app.update()
            frame_count += 1
            if args.max_frames is not None and frame_count >= args.max_frames:
                break
    finally:
        simulation_app.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
