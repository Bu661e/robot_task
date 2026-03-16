# M6 policy_model Todo

Module goal:
- Let the LLM generate Python policy code from task, perception, and robot context.
- Keep all object selection and relation reasoning inside the generated code.

Checklist:
- [ ] Define the `PolicyRequest` and `PolicyCode` schema used by the module.
- [ ] Build `PolicyRequest` from `TaskRequest`, `ParsedTask`, `WorldPerceptionResult`, and `RobotContext`.
- [ ] Design the LLM prompt so the output is restricted to Python only.
- [ ] Enforce the fixed entrypoint `run(robot, perception, named_poses)`.
- [ ] Enforce the single allowed robot API `robot.pick_and_place(...)`.
- [ ] Encode the execution rules for common cases, including:
  - plain "pick up" -> place to `named_poses["hold_pose"]`
  - "place on top of" -> compute `place_z` with the `0.03` safety margin
- [ ] Parse and validate the model output into `PolicyCode` JSON.
- [ ] Save `policy_request.json`, `policy_code.json`, and `policy_code.py`.
- [ ] Reject or sanitize forbidden code patterns such as direct simulator access or unrelated robot APIs.
- [ ] Add tests with canned model outputs for valid code and invalid code.
