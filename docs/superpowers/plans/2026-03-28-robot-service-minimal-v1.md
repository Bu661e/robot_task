# Robot Service Minimal V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable `robot_service` skeleton for a single client, single session, single task flow, with `environment_id` accepted and carried through the API/worker boundary.

**Architecture:** A FastAPI API process owns the external HTTP contract and one in-memory `RobotServiceManager`. The manager launches a single Isaac worker subprocess on session creation, communicates with it via JSON lines over stdin/stdout, and persists artifact metadata locally. The worker side keeps Isaac-specific setup isolated and, for now, loads only a default ground, light, and block while preserving the `environment_id` API surface.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, Uvicorn, pytest

---

### Task 1: Project Scaffold And Runtime Basics

**Files:**
- Create: `robot_service/pyproject.toml`
- Create: `robot_service/__init__.py`
- Create: `robot_service/api/__init__.py`
- Create: `robot_service/common/__init__.py`
- Create: `robot_service/runtime/__init__.py`
- Create: `robot_service/worker/__init__.py`
- Create: `robot_service/runtime/settings.py`
- Create: `robot_service/runtime/logging_config.py`
- Create: `robot_service/runtime/paths.py`
- Create: `robot_service/runtime/ids.py`
- Test: `robot_service/tests/test_runtime.py`

- [ ] **Step 1: Write the failing runtime tests**
- [ ] **Step 2: Run `pytest robot_service/tests/test_runtime.py -v` and verify failure**
- [ ] **Step 3: Add project metadata and runtime helpers**
- [ ] **Step 4: Run `pytest robot_service/tests/test_runtime.py -v` and verify pass**

### Task 2: Shared Schemas And IPC Messages

**Files:**
- Create: `robot_service/common/schemas.py`
- Create: `robot_service/common/messages.py`
- Test: `robot_service/tests/test_schemas.py`

- [ ] **Step 1: Write failing schema/message tests**
- [ ] **Step 2: Run `pytest robot_service/tests/test_schemas.py -v` and verify failure**
- [ ] **Step 3: Implement minimal Pydantic models for HTTP and IPC payloads**
- [ ] **Step 4: Run `pytest robot_service/tests/test_schemas.py -v` and verify pass**

### Task 3: Manager State Machine

**Files:**
- Create: `robot_service/api/manager.py`
- Test: `robot_service/tests/test_manager.py`

- [ ] **Step 1: Write failing manager tests for session/task rules**
- [ ] **Step 2: Run `pytest robot_service/tests/test_manager.py -v` and verify failure**
- [ ] **Step 3: Implement `RobotServiceManager` with single-session and single-task guards**
- [ ] **Step 4: Run `pytest robot_service/tests/test_manager.py -v` and verify pass**

### Task 4: HTTP API Layer

**Files:**
- Create: `robot_service/api/app.py`
- Test: `robot_service/tests/test_app.py`

- [ ] **Step 1: Write failing FastAPI route tests**
- [ ] **Step 2: Run `pytest robot_service/tests/test_app.py -v` and verify failure**
- [ ] **Step 3: Implement FastAPI app factory and route handlers backed by the manager**
- [ ] **Step 4: Run `pytest robot_service/tests/test_app.py -v` and verify pass**

### Task 5: Worker Skeleton

**Files:**
- Create: `robot_service/worker/entrypoint.py`
- Create: `robot_service/worker/environment.py`
- Create: `robot_service/worker/queries.py`
- Create: `robot_service/worker/task_runner.py`
- Test: `robot_service/tests/test_worker_units.py`

- [ ] **Step 1: Write failing worker unit tests that avoid importing real Isaac Sim**
- [ ] **Step 2: Run `pytest robot_service/tests/test_worker_units.py -v` and verify failure**
- [ ] **Step 3: Implement worker-side command handling skeleton with deferred Isaac imports**
- [ ] **Step 4: Run `pytest robot_service/tests/test_worker_units.py -v` and verify pass**

### Task 6: README Sync

**Files:**
- Modify: `robot_service/README.md`

- [ ] **Step 1: Sync implemented file layout and current limitations**
- [ ] **Step 2: Run the focused test suite and verify documentation still matches behavior**

### Task 7: Focused Verification

**Files:**
- Test: `robot_service/tests/test_runtime.py`
- Test: `robot_service/tests/test_schemas.py`
- Test: `robot_service/tests/test_manager.py`
- Test: `robot_service/tests/test_app.py`
- Test: `robot_service/tests/test_worker_units.py`

- [ ] **Step 1: Run `pytest robot_service/tests -v`**
- [ ] **Step 2: Review failures and fix minimally**
- [ ] **Step 3: Re-run `pytest robot_service/tests -v` until green**
