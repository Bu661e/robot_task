#!/bin/bash

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

if [[ -n "${ISAAC_SIM_PYTHON:-}" ]]; then
  ISAAC_PYTHON_CMD="$ISAAC_SIM_PYTHON"
elif [[ -n "${ISAAC_SIM_ROOT:-}" && -x "${ISAAC_SIM_ROOT}/python.sh" ]]; then
  ISAAC_PYTHON_CMD="${ISAAC_SIM_ROOT}/python.sh"
else
  echo "未找到 Isaac Sim Python。请设置 ISAAC_SIM_PYTHON 或 ISAAC_SIM_ROOT。" >&2
  exit 1
fi

cd "$REPO_ROOT"
"$ISAAC_PYTHON_CMD" -m robot.worker_main "$@"
