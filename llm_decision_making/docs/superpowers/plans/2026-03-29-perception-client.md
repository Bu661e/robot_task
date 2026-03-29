# Perception Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first decision-side `perception_client` with typed schemas, runtime config, artifact upload/download, inference requests, and focused tests.

**Architecture:** Keep runtime settings in `config/perception_config.py`, keep shared protocol dataclasses in `utils/perception_schemas.py`, and keep `utils/perception_client.py` as a thin `httpx` wrapper plus run-logger integration. This phase stays isolated from `main.py` and does not take on robot-observation adaptation.

**Tech Stack:** Python 3.11+, `httpx`, `pytest`, dataclasses

---

### Task 1: Add perception runtime config

**Files:**
- Create: `llm_decision_making/config/perception_config.py`
- Test: `llm_decision_making/tests/test_perception_client.py`

- [ ] **Step 1: Write the failing test**

```python
def test_default_perception_client_uses_shared_perception_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PERCEPTION_BASE_URL", "https://perception.example.com")
    monkeypatch.setenv("PERCEPTION_TIMEOUT_S", "12.5")
    monkeypatch.setenv("PERCEPTION_TRUST_ENV", "true")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_perception_client.py::test_default_perception_client_uses_shared_perception_config -q`
Expected: FAIL because `config.perception_config` and default client wiring do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
PERCEPTION_BASE_URL = os.getenv("PERCEPTION_BASE_URL", "http://127.0.0.1:8001")
PERCEPTION_TIMEOUT_S = float(os.getenv("PERCEPTION_TIMEOUT_S", "30.0"))
PERCEPTION_TRUST_ENV = _read_bool_env("PERCEPTION_TRUST_ENV", False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_perception_client.py::test_default_perception_client_uses_shared_perception_config -q`
Expected: PASS


### Task 2: Add typed perception protocol schemas

**Files:**
- Create: `llm_decision_making/utils/perception_schemas.py`
- Test: `llm_decision_making/tests/test_perception_client.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_perception_request_to_dict_serializes_observations() -> None:
    request = PerceptionRequest(...)
    payload = request.to_dict()

    assert payload["observations"][0]["camera_id"] == "table_top"


def test_perception_response_from_dict_parses_detected_objects() -> None:
    response = PerceptionResponse.from_dict(...)

    assert response.observation_results[0].detected_objects[0].label == "blue_cube"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_perception_client.py -k perception_schemas -q`
Expected: FAIL because `utils.perception_schemas` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add request-side dataclasses:
- `ArtifactRef`
- `Intrinsics`
- `Extrinsics`
- `PerceptionObservation`
- `PerceptionTask`
- `PerceptionContext`
- `PerceptionOptions`
- `PerceptionRequest`

Add response-side dataclasses:
- `ArtifactMetadata`
- `DetectedObject`
- `SceneArtifacts`
- `ObservationResult`
- `PerceptionResponse`

Include only the helper functions needed to validate mappings, strings, numbers, lists, datetimes, and optional fields.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_perception_client.py -k perception_schemas -q`
Expected: PASS


### Task 3: Implement `PerceptionClient` HTTP methods

**Files:**
- Modify: `llm_decision_making/utils/perception_client.py`
- Test: `llm_decision_making/tests/test_perception_client.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_perception_client_upload_artifact_posts_multipart_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ...


def test_perception_client_infer_posts_typed_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ...
```

Also add failing tests for:
- `download_artifact(...)`
- default client config wiring
- clear non-2xx error handling
- invalid non-object JSON response handling

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_perception_client.py -q`
Expected: FAIL because methods and helpers are missing.

- [ ] **Step 3: Write minimal implementation**

Implement:
- `PerceptionClientError`
- lazy `httpx.Client` construction
- `_request_json()` helper
- `_raise_for_error_response()` helper
- `upload_artifact(...)`
- `infer(...)`
- `download_artifact(...)`
- `default_perception_client`

Keep `PerceptionClient` protocol-focused:
- accept typed request objects
- serialize with `to_dict()`
- parse responses with `from_dict()`
- do not convert robot camera payloads in this file

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_perception_client.py -q`
Expected: PASS


### Task 4: Add run logger coverage for perception traffic

**Files:**
- Modify: `llm_decision_making/tests/test_perception_client.py`
- Modify: `llm_decision_making/utils/perception_client.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_perception_client_logs_json_and_binary_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_perception_client.py -k run_logger -q`
Expected: FAIL because perception-side logging is not wired yet.

- [ ] **Step 3: Write minimal implementation**

Mirror the established `robot_client` logging pattern:
- `log_http_request()` before request dispatch
- `log_http_response()` after response receipt
- `save_binary_artifact()` for downloads
- summary body for binary downloads with relative path and size

- [ ] **Step 4: Run test to verify it passes**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_perception_client.py -k run_logger -q`
Expected: PASS


### Task 5: Sync module docs and run focused verification

**Files:**
- Modify: `llm_decision_making/README.md`
- Test: `llm_decision_making/tests/test_perception_client.py`

- [ ] **Step 1: Update module docs**

Document:
- new `config/perception_config.py`
- new `utils/perception_schemas.py`
- `perception_client` responsibilities
- this phase boundary: no `main.py` wiring yet

- [ ] **Step 2: Run focused verification**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_perception_client.py -q`
Expected: PASS

- [ ] **Step 3: Run broader regression check**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_robot_client.py tests/test_perception_client.py -q`
Expected: PASS
