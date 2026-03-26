# ParsedTask Keep Instruction Design

**Date:** 2026-03-27

**Goal:** Make `ParsedTask` preserve the original `instruction` from `SourceTask` while keeping object extraction behavior unchanged.

## Context

`TaskParser` currently consumes a `SourceTask` with:

- `task_id`
- `instruction`

but returns a `ParsedTask` with only:

- `task_id`
- `object_texts`

This drops the original task text after parsing, even though downstream stages may still need the exact natural-language instruction alongside extracted object names.

## Decision

Use a direct passthrough field on `ParsedTask`.

- `ParsedTask` will contain:
  - `task_id: str`
  - `instruction: str`
  - `object_texts: list[str]`
- `TaskParser.parse_task()` will copy `task.instruction` directly into the returned `ParsedTask`
- `TaskParser` will not rephrase, normalize, or mutate the instruction field

## Alternatives Considered

### 1. Recommended: add required `instruction` to `ParsedTask`

Pros:
- smallest change
- clear schema ownership
- no compatibility ambiguity

Cons:
- all current `ParsedTask(...)` assertions must be updated

### 2. Add optional `instruction` with a default

Pros:
- fewer immediate call-site updates

Cons:
- weakens schema clarity
- allows partially-migrated code to persist

### 3. Nest the full `SourceTask` inside `ParsedTask`

Pros:
- preserves all source metadata for future use

Cons:
- more schema churn than needed
- heavier object shape for a simple passthrough requirement

## Rationale

The required `instruction` field is the cleanest fit for the current codebase. `ParsedTask` already represents parsed task state, so keeping the original instruction there is consistent and avoids losing source context immediately after parsing.

## Impacted Files

- `modules/schemas.py`
  - add `instruction` to `ParsedTask`
- `modules/task_parser.py`
  - include `task.instruction` when constructing `ParsedTask`
- `tests/test_task_parser.py`
  - assert `instruction` is preserved
- `tests/test_main.py`
  - update `ParsedTask(...)` expectations in parser/process tests
- `README.md`
  - update the `ParsedTask` example and description

## Non-Goals

- No change to `SourceTask`
- No change to CLI arguments or task loading
- No change to the object extraction algorithm
