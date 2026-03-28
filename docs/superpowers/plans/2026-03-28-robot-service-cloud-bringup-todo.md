# Robot Service Cloud Bring-Up TODO

**Branch:** `feature/robot-service`  
**Current commit:** `41e3fdf`  
**Current local verification:** `uv run --project robot_service pytest robot_service/tests -q` -> `18 passed`

## Current State

The repository already contains the first runnable skeleton for `robot_service`:

- `FastAPI` API process
- single active session
- single active task
- single Isaac worker subprocess
- `environment_id` accepted by `POST /sessions` and forwarded to the worker
- placeholder worker environment with default `ground`, `light`, `block`
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
- required display/headless settings are known
- repo branch is `feature/robot-service`

Minimum checks:

```bash
git branch --show-current
pwd
echo "$ISAAC_SIM_ROOT"
ls "$ISAAC_SIM_ROOT"
"$ISAAC_SIM_ROOT/python.sh" --help
```

### 2. Worker Standalone Smoke Test

Before involving the API, verify the worker entrypoint can be launched by Isaac Sim Python:

```bash
"$ISAAC_SIM_ROOT/python.sh" robot_service/worker/entrypoint.py --session-id smoke-session --session-dir /tmp/robot-service-smoke
```

Expected outcome for this stage:

- the process starts
- `SimulationApp` initialization is attempted successfully
- the process can receive a simple JSON command from stdin
- the process can return JSON to stdout

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

After the worker can start on the cloud host, run the API and test the main flow:

1. `POST /sessions`
2. `GET /sessions/{session_id}`
3. `GET /sessions/{session_id}/robot`
4. `GET /sessions/{session_id}/action-apis`
5. `POST /sessions/{session_id}/tasks`
6. `DELETE /sessions/{session_id}`

The first acceptance target is not “robot completes a real pick-and-place”.
The first acceptance target is “API and worker stay coherent under a real Isaac Sim runtime”.

## Concrete TODO

- [ ] Verify cloud host has usable Isaac Sim `5.0.0` and a valid `ISAAC_SIM_ROOT`
- [ ] Run `robot_service/worker/entrypoint.py` directly with `python.sh`
- [ ] Confirm stdin/stdout JSON communication works under real Isaac Sim runtime
- [ ] Replace placeholder environment setup in `robot_service/worker/environment.py` with a real minimal scene
- [ ] Confirm `POST /sessions` moves from `starting` to `ready` on the cloud host
- [ ] Confirm `GET /sessions/{id}/robot` returns a real response under Isaac Sim
- [ ] Confirm `GET /sessions/{id}/action-apis` still returns the placeholder API description
- [ ] Confirm `POST /sessions/{id}/tasks` still goes through the state machine under real worker startup
- [ ] Decide whether camera output should be implemented next or task execution should be implemented next

## Suggested First Commands On The Cloud Host

These are the first commands the next window should likely run after pulling the branch:

```bash
git branch --show-current
git rev-parse --short HEAD
uv run --project robot_service pytest robot_service/tests -q
echo "$ISAAC_SIM_ROOT"
"$ISAAC_SIM_ROOT/python.sh" robot_service/worker/entrypoint.py --session-id smoke-session --session-dir /tmp/robot-service-smoke
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
