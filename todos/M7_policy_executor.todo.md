# M7 policy_executor Todo

Module goal:
- Execute the generated Python code in a controlled environment.
- Call `robot.pick_and_place(...)` through the generated `run(...)` function.
- Convert runtime failures into `ExecutionResult`.

Checklist:
- [ ] Define the `ExecutionResult` schema and the executor-side success/failure mapping.
- [ ] Restrict execution to Python code only.
- [ ] Load code from `PolicyCode` and verify `language == "python"` and `entrypoint == "run"`.
- [ ] Build a controlled runtime that exposes only `robot`, `perception`, `named_poses`, and safe Python basics.
- [ ] Execute `run(robot, perception, named_poses)`.
- [ ] Record which robot API was actually called and verify it is `pick_and_place`.
- [ ] Capture enough execution metadata to fill `selected_object_id`, `executed_api`, and `message` when available.
- [ ] Convert exceptions into a failed `ExecutionResult` instead of crashing the pipeline.
- [ ] Save `execution_result.json` under artifacts.
- [ ] Add tests for success, runtime exception, forbidden API usage, and missing entrypoint.
