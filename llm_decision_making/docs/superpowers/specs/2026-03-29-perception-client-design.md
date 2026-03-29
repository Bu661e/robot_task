# Decision-Side Perception Client Design

**Date:** 2026-03-29

**Goal:** Add decision-side typed schemas and an HTTP client for the shared `llm_decision_making` <-> `perception_service` protocol without changing the main orchestration flow yet.

## Context

The shared protocol already exists in `docs/protocols/llm_decision_making__perception_service.md`, and the current `perception_service` API schema matches it closely.

On the decision side, `utils/perception_client.py` is still empty. The current gap is not protocol design. The gap is:

- runtime config for the perception service endpoint
- typed request and response schemas owned by `llm_decision_making`
- a thin HTTP client that uploads artifacts, submits inference requests, downloads artifacts, and logs traffic under the active run

Recent real robot logs under `llm_decision_making/runs/` also show that robot camera payloads cannot be forwarded directly to perception as-is. For example, robot camera extrinsics currently use `quaternion_xyzw`, while the shared perception protocol requires `quaternion_wxyz`. That adaptation belongs outside the initial client module.

## Decision

Implement the first decision-side perception integration as three focused units:

- `config/perception_config.py`
  - shared runtime config for base URL, timeout, and `trust_env`
- `utils/perception_schemas.py`
  - typed protocol dataclasses for request and response payloads
- `utils/perception_client.py`
  - a thin `httpx` wrapper that only speaks the shared protocol and uses the typed schemas

This phase intentionally does not modify `main.py` and does not introduce robot-to-perception observation conversion logic.

## Client API

`PerceptionClient` will expose three methods:

- `upload_artifact(...) -> ArtifactMetadata`
- `infer(request: PerceptionRequest) -> PerceptionResponse`
- `download_artifact(...) -> bytes`

The client will also expose a module-level `default_perception_client`, wired from `config/perception_config.py`, matching the current `robot_client` pattern.

## Schema Boundaries

`utils/perception_schemas.py` will contain decision-owned dataclasses for the shared protocol instead of importing the server-side pydantic models from `perception_service`.

Request-side schemas:

- `ArtifactRef`
- `Intrinsics`
- `Extrinsics`
- `PerceptionObservation`
- `PerceptionTask`
- `PerceptionContext`
- `PerceptionOptions`
- `PerceptionRequest`

Response-side schemas:

- `ArtifactMetadata`
- `DetectedObject`
- `SceneArtifacts`
- `ObservationResult`
- `PerceptionResponse`

Serialization conventions:

- request-side types provide `to_dict()`
- response-side types provide `from_dict()`
- parsing helpers follow the same explicit style already used in `utils/robot_schemas.py`

## Logging

Perception HTTP traffic will use the existing active run logger and stay inside the pre-created perception folders:

- `perception_service/requests`
- `perception_service/responses`
- `perception_service/artifacts`

This phase keeps the existing logging pattern:

- JSON requests and responses are recorded through the run logger
- binary artifact downloads are saved to `perception_service/artifacts`
- response summaries for binary downloads record relative path and byte size instead of raw content

## Testing

Tests will follow the same style already used for `robot_client`:

- fake `httpx.Client`
- explicit queued fake responses
- direct assertions on typed schema parsing
- run logger assertions through files created under a temp run directory

Coverage for this phase:

- default config wiring
- request serialization for artifact upload and inference
- response parsing for artifact metadata and inference results
- binary artifact download behavior
- non-2xx error handling
- perception run logging

## Non-Goals

- No change to `main.py`
- No robot observation to perception request adapter yet
- No protocol changes in `docs/protocols/`
- No direct import of `perception_service` internal pydantic models into `llm_decision_making`
