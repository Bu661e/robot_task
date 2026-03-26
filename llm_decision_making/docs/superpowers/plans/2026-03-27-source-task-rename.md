# SourceTask Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the task-only schema `TaskDescription` to `SourceTask` everywhere without changing runtime behavior.

**Architecture:** This is a naming-only refactor. The task loader, parser, and main CLI flow keep the same boundaries and data shape; only the schema name and all of its references change. Documentation and internal design/plan docs are updated in the same pass so the repo has a single canonical name.

**Tech Stack:** Python, pytest, Markdown

---

### Task 1: Make tests expect `SourceTask`

**Files:**
- Modify: `tests/test_main.py`
- Modify: `tests/test_task_loader.py`
- Modify: `tests/test_task_parser.py`
- Modify: `tests/test_schemas.py`

- [ ] **Step 1: Replace `TaskDescription` imports and constructor calls with `SourceTask` in tests**

```python
from modules.schemas import ParsedTask, SourceTask

assert task == SourceTask(task_id="2", instruction="Pick up the smallest ball.")
```

- [ ] **Step 2: Update type-hint assertions to require `SourceTask`**

```python
assert get_type_hints(process)["task"] is SourceTask
assert get_type_hints(load_task_from_cli)["return"] == tuple[SourceTask, str]
```

- [ ] **Step 3: Run targeted tests to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_main.py tests/test_task_loader.py tests/test_task_parser.py tests/test_schemas.py -q`
Expected: FAIL because production code still exposes `TaskDescription`

### Task 2: Rename the schema in code

**Files:**
- Modify: `modules/schemas.py`
- Modify: `modules/task_loader.py`
- Modify: `modules/task_parser.py`
- Modify: `main.py`

- [ ] **Step 1: Rename the dataclass in `modules/schemas.py`**

```python
@dataclass(slots=True)
class SourceTask:
    task_id: str
    instruction: str
```

- [ ] **Step 2: Update all imports, annotations, and constructor calls in code**

```python
from modules.schemas import ParsedTask, SourceTask
```

- [ ] **Step 3: Keep behavior unchanged while updating the `__main__` task variable names and annotations**

```python
new_task, objects_env_id = load_task_from_cli(sys.argv[1:])
```

- [ ] **Step 4: Run targeted tests**

Run: `source .venv/bin/activate && pytest tests/test_main.py tests/test_task_loader.py tests/test_task_parser.py tests/test_schemas.py -q`
Expected: PASS

### Task 3: Update docs to the new canonical name

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-03-27-cli-objects-env-id-separation-design.md`
- Modify: `docs/superpowers/plans/2026-03-27-cli-objects-env-id-separation.md`
- Modify: `docs/superpowers/plans/2026-03-27-source-task-rename.md`

- [ ] **Step 1: Replace prose and examples that mention `TaskDescription` with `SourceTask`**

```markdown
`task_loader` 输出是一个自定义的 `SourceTask` 结构。
```

- [ ] **Step 2: Run full verification**

Run: `source .venv/bin/activate && pytest -q`
Expected: PASS
