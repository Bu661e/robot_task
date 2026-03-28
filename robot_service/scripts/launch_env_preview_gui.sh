#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

ISAAC_SIM_ROOT="${ISAAC_SIM_ROOT:-/root/isaacsim}"
ENVIRONMENT_ID="${1:-env-default}"
SESSION_DIR="${ROBOT_SERVICE_GUI_SESSION_DIR:-/tmp/robot-gui-preview-${ENVIRONMENT_ID}}"

if [[ ! -x "${ISAAC_SIM_ROOT}/python.sh" ]]; then
  echo "Isaac Sim launcher not found: ${ISAAC_SIM_ROOT}/python.sh" >&2
  exit 1
fi

mkdir -p "${SESSION_DIR}"
cd "${REPO_ROOT}"

echo "Launching Isaac Sim GUI preview"
echo "  repo_root: ${REPO_ROOT}"
echo "  isaac_sim_root: ${ISAAC_SIM_ROOT}"
echo "  environment_id: ${ENVIRONMENT_ID}"
echo "  session_dir: ${SESSION_DIR}"
echo "  display: ${DISPLAY:-<unset>}"

exec "${ISAAC_SIM_ROOT}/python.sh" - "${ENVIRONMENT_ID}" "${SESSION_DIR}" <<'PY'
import sys
from pathlib import Path

environment_id = sys.argv[1]
session_dir = Path(sys.argv[2])

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": False})

from robot_service.worker.environment import EnvironmentRuntime

runtime = EnvironmentRuntime(session_dir=session_dir, simulation_app=simulation_app)
runtime.load_environment(environment_id)
world = runtime.world

print(f"GUI preview ready: {environment_id} loaded.")
print("Close the Isaac Sim window when you are finished checking the scene.")

try:
    while simulation_app.is_running():
        if world is not None:
            world.step(render=True)
        else:
            simulation_app.update()
finally:
    simulation_app.close()
PY
