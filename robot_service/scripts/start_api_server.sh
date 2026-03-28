#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

HOST="${ROBOT_SERVICE_HOST:-127.0.0.1}"
PORT="${ROBOT_SERVICE_PORT:-18080}"
RUNS_DIR="${RUNS_DIR:-${REPO_ROOT}/robot_service/runs}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
ISAAC_SIM_ROOT="${ISAAC_SIM_ROOT:-/root/isaacsim}"

cd "${REPO_ROOT}"

export ISAAC_SIM_ROOT
export ROBOT_SERVICE_HOST="${HOST}"
export ROBOT_SERVICE_PORT="${PORT}"
export RUNS_DIR
export LOG_LEVEL

exec uv run --project robot_service uvicorn robot_service.api.app:create_app --factory --host "${HOST}" --port "${PORT}"
