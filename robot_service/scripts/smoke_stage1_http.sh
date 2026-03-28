#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

BASE_URL="${ROBOT_SERVICE_BASE_URL:-http://127.0.0.1:18080}"
ENVIRONMENT_ID="${1:-env-default}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="${ROBOT_SERVICE_SMOKE_DIR:-${REPO_ROOT}/robot_service/runs/review/http_smoke_${TIMESTAMP}}"
REQUESTS_DIR="${RUN_DIR}/requests"
RESPONSES_DIR="${RUN_DIR}/responses"
ARTIFACTS_DIR="${RUN_DIR}/artifacts"
LOG_FILE="${RUN_DIR}/run.log"

mkdir -p "${REQUESTS_DIR}" "${RESPONSES_DIR}" "${ARTIFACTS_DIR}"

SESSION_ID=""

log() {
  printf '[%s] %s\n' "$(date --iso-8601=seconds)" "$*" | tee -a "${LOG_FILE}"
}

write_request() {
  local step_name="$1"
  local method="$2"
  local path="$3"
  local body="${4:-}"

  {
    printf 'method=%s\n' "${method}"
    printf 'url=%s%s\n' "${BASE_URL}" "${path}"
    printf 'timestamp=%s\n' "$(date --iso-8601=seconds)"
    if [[ -n "${body}" ]]; then
      printf 'content_type=application/json\n'
      printf 'body=%s\n' "${body}"
    fi
  } > "${REQUESTS_DIR}/${step_name}.txt"
}

request_json() {
  local step_name="$1"
  local method="$2"
  local path="$3"
  local body="${4:-}"
  local headers_file="${RESPONSES_DIR}/${step_name}.headers"
  local body_file="${RESPONSES_DIR}/${step_name}.json"

  write_request "${step_name}" "${method}" "${path}" "${body}"

  if [[ -n "${body}" ]]; then
    curl --fail-with-body -sS -X "${method}" "${BASE_URL}${path}" \
      -H 'Content-Type: application/json' \
      --data "${body}" \
      -D "${headers_file}" \
      -o "${body_file}"
  else
    curl --fail-with-body -sS -X "${method}" "${BASE_URL}${path}" \
      -D "${headers_file}" \
      -o "${body_file}"
  fi
}

download_artifact() {
  local artifact_id="$1"
  local content_type="$2"
  local extension
  local headers_file="${RESPONSES_DIR}/artifact_${artifact_id}.headers"
  local request_file="${REQUESTS_DIR}/artifact_${artifact_id}.txt"

  case "${content_type}" in
    image/png)
      extension="png"
      ;;
    application/x-npy)
      extension="npy"
      ;;
    *)
      extension="bin"
      ;;
  esac

  {
    printf 'method=GET\n'
    printf 'url=%s/artifacts/%s\n' "${BASE_URL}" "${artifact_id}"
    printf 'timestamp=%s\n' "$(date --iso-8601=seconds)"
  } > "${request_file}"

  curl --fail-with-body -sS -X GET "${BASE_URL}/artifacts/${artifact_id}" \
    -D "${headers_file}" \
    -o "${ARTIFACTS_DIR}/${artifact_id}.${extension}"
}

cleanup() {
  if [[ -n "${SESSION_ID}" ]]; then
    log "Cleaning up session ${SESSION_ID}"
    request_json "delete_session_cleanup" "DELETE" "/sessions/${SESSION_ID}" || true
  fi
}

trap cleanup EXIT

log "Running stage-1 HTTP smoke test"
log "Base URL: ${BASE_URL}"
log "Environment ID: ${ENVIRONMENT_ID}"
log "Run dir: ${RUN_DIR}"

CREATE_SESSION_BODY="$(python3 - <<'PY' "${ENVIRONMENT_ID}"
import json
import sys

environment_id = sys.argv[1]
print(json.dumps({"backend_type": "isaac_sim", "environment_id": environment_id, "ext": {}}, ensure_ascii=False))
PY
)"

request_json "create_session" "POST" "/sessions" "${CREATE_SESSION_BODY}"

SESSION_ID="$(python3 - <<'PY' "${RESPONSES_DIR}/create_session.json"
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)
print(data["session_id"])
PY
)"

log "Created session: ${SESSION_ID}"

request_json "get_session" "GET" "/sessions/${SESSION_ID}"
request_json "get_robot" "GET" "/sessions/${SESSION_ID}/robot"
request_json "get_cameras" "GET" "/sessions/${SESSION_ID}/cameras"

python3 - <<'PY' "${RESPONSES_DIR}/get_cameras.json" "${RUN_DIR}/artifact_manifest.json"
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)

manifest = []
for camera in data.get("cameras", []):
    rgb = camera["rgb_image"]
    depth = camera["depth_image"]
    manifest.append(
        {
            "camera_id": camera["camera_id"],
            "artifacts": [
                {"kind": "rgb", "artifact_id": rgb["artifact_id"], "content_type": rgb["content_type"]},
                {"kind": "depth", "artifact_id": depth["artifact_id"], "content_type": depth["content_type"]},
            ],
        }
    )

with open(sys.argv[2], "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
PY

while IFS=$'\t' read -r artifact_id content_type; do
  [[ -z "${artifact_id}" ]] && continue
  log "Downloading artifact ${artifact_id} (${content_type})"
  download_artifact "${artifact_id}" "${content_type}"
done < <(
  python3 - <<'PY' "${RUN_DIR}/artifact_manifest.json"
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    manifest = json.load(f)

for camera in manifest:
    for artifact in camera["artifacts"]:
        print(f'{artifact["artifact_id"]}\t{artifact["content_type"]}')
PY
)

request_json "delete_session" "DELETE" "/sessions/${SESSION_ID}"
log "Deleted session: ${SESSION_ID}"
SESSION_ID=""

python3 - <<'PY' "${RUN_DIR}"
import json
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
artifacts_dir = run_dir / "artifacts"
summary = {
    "run_dir": str(run_dir),
    "artifact_files": sorted(
        [
            {
            "name": path.name,
            "size_bytes": path.stat().st_size,
        }
            for path in artifacts_dir.iterdir()
            if path.is_file()
        ],
        key=lambda item: item["name"],
    ),
}

with open(run_dir / "summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)
PY

log "Smoke test completed successfully"
