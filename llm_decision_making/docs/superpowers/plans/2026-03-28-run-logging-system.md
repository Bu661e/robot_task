# Run Logging System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a simple run-based logging system that writes terminal summaries plus complete file logs, separates robot and perception HTTP logs, and stores binary artifacts under per-run directories.

**Architecture:** Add a dedicated `utils/run_logging.py` module that owns run directory creation, dual terminal/file logging, full request/response persistence, and binary artifact storage. `main.py` initializes a run logger for each CLI execution, `robot_client.py` records HTTP traffic through the active run logger, and the system pre-creates both `robot_service/` and `perception_service/` folders for future use.

**Tech Stack:** Python 3.11+, standard library `logging`, `pathlib`, `json`, `pytest`

---

### Task 1: Add failing tests for run directory layout and dual logging

**Files:**
- Create: `llm_decision_making/tests/test_run_logging.py`
- Create: `llm_decision_making/utils/run_logging.py`
- Create: `llm_decision_making/config/run_logging_config.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_start_run_logging_creates_expected_run_directories(tmp_path: Path) -> None:
    ...

def test_run_logger_writes_console_summary_and_full_file_log(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ...
```

Cover:
- `runs/<timestamp>_task-<task_id>/`
- `run.log`
- `robot_service/requests`
- `robot_service/responses`
- `robot_service/artifacts`
- `perception_service/requests`
- `perception_service/responses`
- `perception_service/artifacts`
- terminal only shows summary
- `run.log` contains full text payload

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_run_logging.py -q`
Expected: FAIL because run logging module and config do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement:
- `RUNS_DIR` in `config/run_logging_config.py`
- `RunPaths`, `ServicePaths`, `RunLogger`
- `start_run_logging()`, `get_active_run_logger()`, `clear_active_run_logger()`
- terminal/file dual formatter with summary vs full text

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_run_logging.py -q`
Expected: PASS


### Task 2: Add failing tests for HTTP request/response persistence and artifact storage

**Files:**
- Modify: `llm_decision_making/tests/test_run_logging.py`
- Modify: `llm_decision_making/utils/run_logging.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_service_logger_persists_full_http_request_and_response(tmp_path: Path) -> None:
    ...

def test_service_logger_saves_binary_artifact_and_logs_path_and_size(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_run_logging.py -q`
Expected: FAIL because persistence helpers are missing.

- [ ] **Step 3: Write minimal implementation**

Implement per-service helpers for:
- full request JSON file
- full response JSON file
- binary artifact file storage
- console summary only for binary artifact path/size

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_run_logging.py -q`
Expected: PASS


### Task 3: Integrate robot client HTTP logging

**Files:**
- Modify: `llm_decision_making/utils/robot_client.py`
- Modify: `llm_decision_making/tests/test_robot_client.py`

- [ ] **Step 1: Write the failing tests**

Add tests proving:
- JSON request/response are written under `robot_service/requests` and `robot_service/responses`
- binary artifact downloads are written under `robot_service/artifacts`
- console output contains only summaries

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_robot_client.py -q`
Expected: FAIL because robot client does not talk to the run logger yet.

- [ ] **Step 3: Write minimal implementation**

Integrate `robot_client.py` with the active run logger:
- record full JSON requests/responses
- record artifact download response summary
- save binary artifact content under the robot service artifact directory

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_robot_client.py -q`
Expected: PASS


### Task 4: Integrate run logging into `main.py`

**Files:**
- Modify: `llm_decision_making/main.py`
- Modify: `llm_decision_making/tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

Add tests proving:
- each CLI execution creates an active run logger using `task.task_id`
- task input and parsed task output are written to `run.log`
- the active run logger is cleared after the run

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_main.py -q`
Expected: FAIL because main does not initialize or use the run logger yet.

- [ ] **Step 3: Write minimal implementation**

Update `main.py` to:
- start run logging after task load
- log task input and parsed task output/data flow
- clear the active run logger at the end

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_main.py -q`
Expected: PASS


### Task 5: Sync README and run full verification

**Files:**
- Modify: `llm_decision_making/README.md`
- Test: `llm_decision_making/tests/test_run_logging.py`
- Test: `llm_decision_making/tests/test_robot_client.py`
- Test: `llm_decision_making/tests/test_main.py`

- [ ] **Step 1: Update README**

Document:
- run as the logging root unit
- directory layout under `runs/`
- terminal summary vs file full-text logging
- robot/perception service folder split
- artifact storage behavior

- [ ] **Step 2: Run focused verification**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_run_logging.py tests/test_robot_client.py tests/test_main.py -q`
Expected: PASS

- [ ] **Step 3: Run full verification**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest -q`
Expected: PASS
