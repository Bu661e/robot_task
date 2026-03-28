# Robot Client Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first-phase `robot_client` HTTP client for session, robot status, camera observations, and artifact download using typed schemas under `utils/`.

**Architecture:** Keep `RobotClient` as a thin HTTP wrapper in `utils/robot_client.py` and move robot protocol parsing into a dedicated `utils/robot_schemas.py` module. Runtime connection settings live in `config/robot_config.py`, while `main.py` only resolves a configured client instance and does not take on session orchestration in this phase.

**Tech Stack:** Python 3.11+, `httpx`, `pytest`, dataclasses

---

### Task 1: Add robot runtime config

**Files:**
- Create: `llm_decision_making/config/robot_config.py`
- Test: `llm_decision_making/tests/test_robot_client.py`

- [ ] **Step 1: Write the failing test**

```python
def test_default_robot_client_uses_shared_robot_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ROBOT_BASE_URL", "https://robot.example.com")
    monkeypatch.setenv("ROBOT_BACKEND_TYPE", "isaac_sim")
    monkeypatch.setenv("ROBOT_TIMEOUT_S", "12.5")
    monkeypatch.setenv("ROBOT_TRUST_ENV", "true")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_robot_client.py::test_default_robot_client_uses_shared_robot_config -q`
Expected: FAIL because `config.robot_config` and default robot client wiring do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
ROBOT_BASE_URL = os.getenv("ROBOT_BASE_URL", "http://127.0.0.1:8000")
ROBOT_BACKEND_TYPE = os.getenv("ROBOT_BACKEND_TYPE", "isaac_sim")
ROBOT_TIMEOUT_S = float(os.getenv("ROBOT_TIMEOUT_S", "30.0"))
ROBOT_TRUST_ENV = _read_bool_env("ROBOT_TRUST_ENV", False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_robot_client.py::test_default_robot_client_uses_shared_robot_config -q`
Expected: PASS


### Task 2: Add typed robot protocol schemas in `utils`

**Files:**
- Create: `llm_decision_making/utils/robot_schemas.py`
- Test: `llm_decision_making/tests/test_robot_client.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_camera_observation_response_parses_depth_image_in_ext() -> None:
    response = CameraObservationResponse.from_dict(
        {
            "session_id": "sess_1",
            "timestamp": "2026-03-28T10:00:00Z",
            "cameras": [
                {
                    "camera_id": "front",
                    "rgb_image": {
                        "content_type": "image/png",
                        "artifact_id": "artifact_rgb_1",
                    },
                    "intrinsics": {
                        "fx": 1.0,
                        "fy": 2.0,
                        "cx": 3.0,
                        "cy": 4.0,
                        "width": 640,
                        "height": 480,
                    },
                    "extrinsics": {
                        "translation": [0.0, 0.0, 1.0],
                        "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
                    },
                    "ext": {
                        "depth_image": {
                            "content_type": "image/png",
                            "artifact_id": "artifact_depth_1",
                        }
                    },
                }
            ],
            "ext": {},
        }
    )

    assert response.cameras[0].ext.depth_image is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_robot_client.py -k robot_schemas -q`
Expected: FAIL because `utils.robot_schemas` and parsing helpers do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(slots=True)
class ArtifactRef:
    content_type: str
    artifact_id: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> ArtifactRef:
        return cls(
            content_type=str(payload["content_type"]),
            artifact_id=str(payload["artifact_id"]),
        )
```

Add the rest of the minimal first-phase schema set:
- `SessionInfo`
- `CloseSessionResponse`
- `RobotStatusResponse`
- `CameraIntrinsics`
- `CameraExtrinsics`
- `CameraExt`
- `CameraObservation`
- `CameraObservationResponse`

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_robot_client.py -k robot_schemas -q`
Expected: PASS


### Task 3: Implement `RobotClient` first-phase HTTP methods

**Files:**
- Modify: `llm_decision_making/utils/robot_client.py`
- Test: `llm_decision_making/tests/test_robot_client.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_robot_client_create_session_posts_backend_and_environment() -> None:
    client = RobotClient(
        base_url="https://robot.example.com",
        backend_type="isaac_sim",
        timeout_s=15.0,
        trust_env=False,
    )

    response = client.create_session(environment_id="2-ycb")

    assert response.session_id == "sess_1"
```

Also add failing tests for:
- `get_session(session_id)`
- `close_session(session_id)`
- `get_robot(session_id)`
- `get_cameras(session_id)`
- `download_artifact(artifact_id)`
- non-2xx responses raising a clear exception

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_robot_client.py -q`
Expected: FAIL because methods and error handling are missing.

- [ ] **Step 3: Write minimal implementation**

```python
class RobotClient:
    def create_session(self, environment_id: str) -> SessionInfo:
        response = self._get_client().post(
            "/sessions",
            json={
                "backend_type": self._backend_type,
                "environment_id": environment_id,
                "ext": {},
            },
        )
        return SessionInfo.from_dict(self._parse_json_response(response))
```

Add the remaining first-phase methods plus:
- lazy `httpx.Client` construction
- shared `_request_json()` helper
- binary artifact download helper
- `RobotClientError` for HTTP/protocol failures

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_robot_client.py -q`
Expected: PASS


### Task 4: Wire shared client usage in `main.py`

**Files:**
- Modify: `llm_decision_making/main.py`
- Modify: `llm_decision_making/utils/robot_client.py`
- Test: `llm_decision_making/tests/test_main.py`

- [ ] **Step 1: Write the failing test**

```python
def test_main_uses_default_robot_client_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ...
```

Keep the assertion narrow: `__main__` path should resolve a configured client object instead of constructing `RobotClient()` with no arguments.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_main.py -k robot_client -q`
Expected: FAIL because `main.py` still instantiates `RobotClient()` directly.

- [ ] **Step 3: Write minimal implementation**

```python
from utils.robot_client import RobotClient, default_robot_client

...
robot_client = default_robot_client
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_main.py -k robot_client -q`
Expected: PASS


### Task 5: Sync documentation and run focused verification

**Files:**
- Modify: `llm_decision_making/README.md`
- Test: `llm_decision_making/tests/test_robot_client.py`
- Test: `llm_decision_making/tests/test_main.py`

- [ ] **Step 1: Update README**

Document:
- first-phase `robot_client` scope
- `utils/robot_schemas.py` as the robot protocol schema location
- required env vars from `config/robot_config.py`
- task APIs remaining for phase 2

- [ ] **Step 2: Run focused verification**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest tests/test_robot_client.py tests/test_main.py -q`
Expected: PASS

- [ ] **Step 3: Run full module verification**

Run: `cd llm_decision_making && source .venv/bin/activate && pytest -q`
Expected: PASS
