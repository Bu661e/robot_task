# CLI Objects Env ID Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `objects_env_id` out of task YAML and `SourceTask`, require it as a CLI argument, and update tests and docs accordingly.

**Architecture:** Keep `SourceTask` as task-only business data and treat `objects_env_id` as runtime input provided by CLI. `TaskLoader` remains responsible only for reading task definitions, while `main.py` is responsible for combining CLI inputs with loader output. `process()` continues to operate on `SourceTask` only, and `robot_client` creation remains outside this change.

**Tech Stack:** Python, argparse, pytest, YAML

---

### Task 1: Update tests to express the new task/runtime boundary

**Files:**
- Modify: `tests/test_main.py`
- Modify: `tests/test_task_loader.py`
- Modify: `tests/test_task_parser.py`

- [ ] **Step 1: Write the failing test expectations in `tests/test_main.py`**

```python
def test_load_task_from_cli_returns_task_and_objects_env_id() -> None:
    task, objects_env_id = load_task_from_cli(
        ["--task-id", "2", "--objects-env-id", "2-ycb"]
    )

    assert task == SourceTask(
        task_id="2",
        instruction="Pick up the smallest ball.",
    )
    assert objects_env_id == "2-ycb"
```

- [ ] **Step 2: Update the existing custom-file and `process()` tests in `tests/test_main.py`**

```python
task = SourceTask(
    task_id="manual",
    instruction="Do not load from CLI.",
)
assert process(task, robot_client=object()) == ParsedTask(...)
```

- [ ] **Step 3: Add a failing CLI validation test in `tests/test_main.py`**

```python
def test_load_task_from_cli_requires_objects_env_id() -> None:
    with pytest.raises(SystemExit):
        load_task_from_cli(["--task-id", "2"])
```

- [ ] **Step 4: Update `tests/test_task_loader.py` to require only task fields**

```python
assert TaskLoader().load_from_cli(task_file=task_file, task_id="2") == SourceTask(
    task_id="2",
    instruction="Pick up the smallest ball.",
)
```

- [ ] **Step 5: Update `tests/test_task_parser.py` fixtures to build `SourceTask` without `objects_env_id`**

```python
SourceTask(
    task_id="1",
    instruction="Pick up the tallest bottle on the table",
)
```

- [ ] **Step 6: Run targeted tests to verify they fail for the expected reason**

Run: `pytest tests/test_main.py tests/test_task_loader.py tests/test_task_parser.py -q`
Expected: FAIL because current code still requires `objects_env_id` in YAML and the CLI signature still returns a single `SourceTask`

### Task 2: Implement the schema and loader changes

**Files:**
- Modify: `modules/schemas.py`
- Modify: `modules/task_loader.py`

- [ ] **Step 1: Remove `objects_env_id` from `SourceTask` in `modules/schemas.py`**

```python
@dataclass(slots=True)
class SourceTask:
    task_id: str
    instruction: str
```

- [ ] **Step 2: Update `TaskLoader.load_from_cli()` to return a task-only `SourceTask`**

```python
return SourceTask(
    task_id=str(task_entry["task_id"]),
    instruction=str(task_entry["instruction"]),
)
```

- [ ] **Step 3: Update YAML validation to require only `task_id` and `instruction`**

```python
required_fields = {"task_id", "instruction"}
```

- [ ] **Step 4: Run targeted tests to verify loader and parser tests pass**

Run: `pytest tests/test_task_loader.py tests/test_task_parser.py -q`
Expected: PASS

### Task 3: Implement the CLI boundary in `main.py`

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py`

- [ ] **Step 1: Add a failing test assertion for the new return type annotation**

```python
assert get_type_hints(load_task_from_cli)["return"] == tuple[SourceTask, str]
```

- [ ] **Step 2: Add required `--objects-env-id` to the CLI parser**

```python
parser.add_argument(
    "--objects-env-id",
    required=True,
    help="Environment identifier used to initialize the robot client.",
)
```

- [ ] **Step 3: Make `RobotClient` resolvable in `main.py` annotations and placeholders**

```python
from utils.robot_client import RobotClient
```

- [ ] **Step 4: Return `(task, args.objects_env_id)` from `load_task_from_cli()`**

```python
task = task_loader.load_from_cli(task_file=args.task_file, task_id=args.task_id)
return task, args.objects_env_id
```

- [ ] **Step 5: Keep `process(task, robot_client)` task-only and update `__main__` call flow**

```python
task, objects_env_id = load_task_from_cli(sys.argv[1:])
# robot_client creation using objects_env_id stays outside process()
```

- [ ] **Step 6: Run targeted main tests**

Run: `pytest tests/test_main.py -q`
Expected: PASS

### Task 4: Update task samples and README

**Files:**
- Modify: `tasks/tasks_en.yaml`
- Modify: `README.md`

- [ ] **Step 1: Remove `objects_env_id` from `tasks/tasks_en.yaml`**

```yaml
- task_id: "1"
  instruction: "Pick up the tallest box."
```

- [ ] **Step 2: Update README CLI documentation and `SourceTask` example**

```json
{
  "task_id": "1",
  "instruction": "Pick up the tallest bottle on the table"
}
```

- [ ] **Step 3: Document that `--objects-env-id` is required CLI input used before `process()`**

```text
CLI 读取任务文件后，还必须通过 --objects-env-id 提供运行环境 id。
```

- [ ] **Step 4: Run targeted tests plus a final focused regression suite**

Run: `pytest tests/test_main.py tests/test_task_loader.py tests/test_task_parser.py tests/test_schemas.py -q`
Expected: PASS
