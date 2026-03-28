# Robot Service Cloud Bring-Up TODO

**Branch:** `feature/robot-service`
**Original local handoff commit:** `41e3fdf`
**Current cloud-host review head:** `0947719`
**Cloud host Isaac Sim root:** `/root/isaacsim`
**Current non-GPU verification:** `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --project robot_service pytest robot_service/tests -q` -> `22 passed`
**Current cloud verification (`2026-03-28`):**
- worker standalone smoke succeeded with `/root/isaacsim/python.sh -m robot_service.worker.entrypoint`
- real `SimulationApp` startup succeeded on the cloud host
- one internal API smoke succeeded on `127.0.0.1:18080` before the public API was narrowed to first-phase scope

## Cloud Host Notes

- On this cloud host, the Isaac Sim launcher script is `/root/isaacsim/python.sh`.
- `ISAAC_SIM_ROOT` is not exported by default in the current shell, so bring-up commands should set it explicitly.
- Do not start Isaac Sim with `python.sh` until the cloud GPU/runtime prerequisite is ready.
- The worker should be launched as a module with `-m robot_service.worker.entrypoint`, not by passing `robot_service/worker/entrypoint.py` as a script path.
- Under the real `python.sh` runtime on this host, PTY-backed IPC is more reliable than plain stdin/stdout pipes.
- Worker stdout may include Isaac/Kit logs and ANSI control sequences before JSON events, so the manager must ignore/sanitize non-JSON lines.

## Current State

The repository already contains the first runnable skeleton for `robot_service`:

- `FastAPI` API process
- single active session
- single active task
- single Isaac worker subprocess using PTY-backed IPC
- `environment_id` accepted by `POST /sessions` and forwarded to the worker
- minimal real worker environment with default `ground`, `light`, `block`
- placeholder task execution path

Current key files:

- `robot_service/api/app.py`
- `robot_service/api/manager.py`
- `robot_service/common/schemas.py`
- `robot_service/common/messages.py`
- `robot_service/worker/entrypoint.py`
- `robot_service/worker/environment.py`
- `robot_service/worker/queries.py`
- `robot_service/worker/task_runner.py`

## Important Constraints

- There is only one client.
- At most one session can exist at a time.
- At most one Isaac Sim instance can exist at a time.
- At most one task can run at a time.
- The frontend may block duplicate task submissions, but the backend must keep its own protection logic.
- Do not redesign this into multi-session, multi-worker, queue-based architecture unless requirements change.

## Goal Of The Next Phase

Bring the current skeleton to the cloud Linux host and verify the **real Isaac Sim 5.0.0 startup path** before writing more Isaac-specific business logic.

The next phase is **not**:

- adding multiple workers
- adding a task queue
- adding database persistence
- implementing full tabletop object layouts for all `environment_id`

The next phase **is**:

- proving `$ISAAC_SIM_ROOT/python.sh` can actually launch the worker
- proving `SimulationApp` can initialize on the target cloud machine
- replacing placeholder environment loading with a minimal real Isaac scene
- keeping `environment_id` in the API even if the real scene still uses a minimal default layout

## Recommended Execution Order

### 1. Cloud Environment Check

Confirm on the cloud host:

- Isaac Sim version is really `5.0.0`
- `python.sh` path is known
- GPU is visible
- GPU/runtime startup has been completed before any Isaac Sim bring-up attempt
- required display/headless settings are known
- repo branch is `feature/robot-service`

Minimum checks:

```bash
git branch --show-current
git rev-parse --short HEAD
pwd
export ISAAC_SIM_ROOT=/root/isaacsim
echo "$ISAAC_SIM_ROOT"
ls "$ISAAC_SIM_ROOT"
cat "$ISAAC_SIM_ROOT/VERSION"
nvidia-smi
```

### 2. Worker Standalone Smoke Test

Do not run this section until the cloud GPU/runtime prerequisite is satisfied.

Before involving the API, verify the worker entrypoint can be launched by Isaac Sim Python and can complete one JSON round-trip:

```bash
mkdir -p /tmp/robot-service-smoke
printf '%s\n' '{"request_id":"req-smoke","command_type":"load_environment","payload":{"environment_id":"env-default"}}' \
  | "$ISAAC_SIM_ROOT/python.sh" -m robot_service.worker.entrypoint \
      --session-id smoke-session \
      --session-dir /tmp/robot-service-smoke
```

Expected outcome for this stage:

- the process starts
- `SimulationApp` initialization is attempted successfully
- the process can receive one JSON command from stdin
- the process can return one `environment_loaded` JSON event to stdout

If this fails, stop and fix worker startup first. Do not continue into API work.

### 3. Minimal Real Isaac Environment

Replace the placeholder `EnvironmentRuntime.load_environment()` logic with the smallest real scene that is practical on the cloud host.

Minimum target:

- ground
- light
- one default block or cuboid

Still keep:

- `environment_id` accepted and stored
- `environment_id` passed through the API to the worker

Do **not** expand to full tabletop object presets yet unless the minimum scene is already stable.

### 4. API To Worker Real Bring-Up

After the worker can start on the cloud host, run the API and test the current first-phase public flow:

1. `POST /sessions`
2. `GET /sessions/{session_id}`
3. `GET /sessions/{session_id}/robot`
4. `GET /sessions/{session_id}/cameras`
5. `DELETE /sessions/{session_id}`

Historical note:

- before the public API was narrowed to first-phase scope, the internal placeholder `action-apis/tasks` flow was also smoke-tested once on the cloud host

The first acceptance target is not “robot completes a real pick-and-place”.
The first acceptance target is “API and worker stay coherent under a real Isaac Sim runtime”.

## Concrete TODO

- [x] Verify cloud host has usable Isaac Sim `5.0.0`, a valid `ISAAC_SIM_ROOT`, and a ready GPU/runtime
- [x] Run `robot_service.worker.entrypoint` with `python.sh -m` after the GPU/runtime prerequisite is met
- [x] Confirm one stdin/stdout JSON round-trip works under real Isaac Sim runtime
- [x] Replace placeholder environment setup in `robot_service/worker/environment.py` with a real minimal scene
- [x] Confirm `POST /sessions` moves from `starting` to `ready` on the cloud host
- [x] Confirm `GET /sessions/{id}/robot` returns a real response under Isaac Sim
- [ ] Confirm `GET /sessions/{id}/cameras` returns a worker-backed response under real Isaac Sim
- [ ] Confirm `GET /artifacts/{artifact_id}` works once real camera artifacts are produced
- [ ] Implement the first-phase camera/depth output path next

## Suggested First Commands On The Cloud Host

These are the first commands the next window should likely run after pulling the branch, before trying to start Isaac Sim:

```bash
git branch --show-current
git rev-parse --short HEAD
export ISAAC_SIM_ROOT=/root/isaacsim
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --project robot_service pytest robot_service/tests -q
echo "$ISAAC_SIM_ROOT"
ls "$ISAAC_SIM_ROOT/python.sh"
cat "$ISAAC_SIM_ROOT/VERSION"
nvidia-smi
```

Only after the GPU/runtime prerequisite is ready:

```bash
mkdir -p /tmp/robot-service-smoke
printf '%s\n' '{"request_id":"req-smoke","command_type":"load_environment","payload":{"environment_id":"env-default"}}' \
  | "$ISAAC_SIM_ROOT/python.sh" -m robot_service.worker.entrypoint \
      --session-id smoke-session \
      --session-dir /tmp/robot-service-smoke
```

## Acceptance Criteria For The Next Phase

The next phase should be considered successful only if all of the following are true:

- worker can be started by Isaac Sim `python.sh` on the cloud host
- `SimulationApp` startup is verified on the target environment
- `POST /sessions` can create a real worker-backed session
- minimal real scene loading works
- current single-session and single-task rules still hold

## Known Gaps To Preserve

These gaps are known and acceptable for now:

- no full `environment_id` -> tabletop object mapping yet
- no real camera artifact output yet
- no real pick-and-place execution yet
- no real running-task cancellation yet

Do not treat these as blockers for the cloud bring-up phase.
