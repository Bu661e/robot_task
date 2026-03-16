# M1 task_parser Todo

Module goal:
- Extract only the object names involved in the instruction.
- Do not parse actions, spatial relations, or target selection logic.
- Ignore `table` / `桌子` by default.

Checklist:
- [x] Define the input/output schema for `TaskRequest` and `ParsedTask`.
- [x] Clarify the parsing rule: only generate `object_texts`, do not encode action or relation semantics.
- [x] Implement object extraction with deduplication while preserving a stable order.
- [x] Implement the default ignore rule for `table` / `桌子`.
- [x] Handle both English and Chinese instructions well enough for the initial closed loop.
- [x] Save `parsed_task.json` under the run artifact directory.
- [x] Add tests for the spec examples:
  - `Pick up the tallest bottle on the table` -> `["bottle"]`
  - `Place the blue_cube on top of the red_cube` -> `["blue_cube", "red_cube"]`
- [x] Add edge-case tests for repeated object mentions and empty extraction results.
