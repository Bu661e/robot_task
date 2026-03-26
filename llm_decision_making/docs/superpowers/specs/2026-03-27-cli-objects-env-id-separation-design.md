# CLI Objects Env ID Separation Design

**Date:** 2026-03-27

**Goal:** Remove `objects_env_id` from task YAML content and `SourceTask`, and require it as a CLI runtime argument instead.

## Context

The current implementation mixes two kinds of data inside `SourceTask`:

- task content: `task_id`, `instruction`
- runtime environment selection: `objects_env_id`

This makes task files carry execution environment details that should be provided when starting a run.

## Decision

For the current CLI flow, use CLI as the only source of `objects_env_id`.

- `SourceTask` keeps only task content fields:
  - `task_id: str`
  - `instruction: str`
- `tasks/*.yaml` keeps only `task_id` and `instruction`
- old YAML entries that still include `objects_env_id` are rejected explicitly, so stale env ids cannot be mistaken as effective input
- `main.py` requires a new CLI argument:
  - `--objects-env-id`
  - value is trimmed and must remain non-empty
- `load_task_from_cli(argv)` returns:
  - `tuple[SourceTask, str]`
- `process()` keeps the current shape of task-only business input:
  - `process(task: SourceTask, robot_client: RobotClient) -> ParsedTask`
- `robot_client` creation remains outside `process()` and outside this change
- when passed to `robot_service`, this runtime value maps to the protocol field `environment_id`

For a future HTTP task entrypoint, the environment id should also remain a separate runtime field rather than being reintroduced into `SourceTask`.

## Rationale

This keeps task semantics and runtime environment semantics separate without introducing an extra wrapper schema. It follows the user's requested flow:

1. load a pure task description from YAML
2. read and validate `objects_env_id` from CLI
3. create `robot_client` before `process()`
4. pass only `SourceTask` into `process()`

## Impacted Files

- `modules/schemas.py`
  - remove `objects_env_id` from `SourceTask`
- `modules/task_loader.py`
  - read only `task_id` and `instruction` from YAML
- `main.py`
  - add required `--objects-env-id`
  - change `load_task_from_cli()` return type to `tuple[SourceTask, str]`
  - keep `process()` task-only
- `tasks/tasks_en.yaml`
  - remove `objects_env_id` fields
- `tests/test_main.py`
  - verify required CLI argument and tuple return
- `tests/test_task_loader.py`
  - verify YAML no longer requires `objects_env_id`
- `tests/test_task_parser.py`
  - construct `SourceTask` without `objects_env_id`
- `README.md`
  - update CLI, schema examples, and data flow description

## Non-Goals

- No change to `robot_client` construction details
- No change to remote HTTP protocol documents
- No new runtime wrapper schema such as `TaskRunInput`
