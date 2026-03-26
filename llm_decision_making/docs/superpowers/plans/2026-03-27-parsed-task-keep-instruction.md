# ParsedTask Keep Instruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `instruction` to `ParsedTask` and have `TaskParser` preserve the original `SourceTask.instruction` in its output.

**Architecture:** Keep the current parser flow unchanged except for extending the output schema. `TaskParser` still extracts `object_texts` the same way, but now returns a richer `ParsedTask` containing both the original instruction and the parsed object list. Update tests and README in the same change so the new schema is the only documented contract.

**Tech Stack:** Python, pytest, dataclasses, Markdown

---

### Task 1: Update tests to require `ParsedTask.instruction`

**Files:**
- Modify: `tests/test_task_parser.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Write failing `ParsedTask` expectations in `tests/test_task_parser.py`**

```python
assert parsed_task == ParsedTask(
    task_id="1",
    instruction="Pick up the tallest bottle on the table",
    object_texts=["bottle"],
)
```

- [ ] **Step 2: Update the `process()` expectation in `tests/test_main.py`**

```python
assert process(task, robot_client=object()) == ParsedTask(
    task_id="manual",
    instruction="Do not load from CLI.",
    object_texts=["bottle"],
)
```

- [ ] **Step 3: Run targeted tests to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_task_parser.py tests/test_main.py -q`
Expected: FAIL because `ParsedTask` does not yet define `instruction`

### Task 2: Extend the parser output schema

**Files:**
- Modify: `modules/schemas.py`
- Modify: `modules/task_parser.py`

- [ ] **Step 1: Add `instruction: str` to `ParsedTask`**

```python
@dataclass(slots=True)
class ParsedTask:
    task_id: str
    instruction: str
    object_texts: list[str]
```

- [ ] **Step 2: Preserve `task.instruction` when constructing `ParsedTask`**

```python
return ParsedTask(
    task_id=task.task_id,
    instruction=task.instruction,
    object_texts=object_texts,
)
```

- [ ] **Step 3: Run targeted tests**

Run: `source .venv/bin/activate && pytest tests/test_task_parser.py tests/test_main.py -q`
Expected: PASS

### Task 3: Update documentation and run full verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the `ParsedTask` example and description in `README.md`**

```json
{
  "task_id": "1",
  "instruction": "Pick up the tallest bottle on the table",
  "object_texts": ["bottle"]
}
```

- [ ] **Step 2: Run full verification**

Run: `source .venv/bin/activate && pytest -q`
Expected: PASS
