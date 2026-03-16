# M3 robot_config_provider Todo

Module goal:
- Provide a preset robot context.
- Do not read the robot context from the simulator.

Checklist:
- [ ] Define the `RobotContext` schema used by the rest of the pipeline.
- [ ] Fill the fixed fields: `coordinate_frame`, `robot_name`, and `api_spec`.
- [ ] Restrict `api_spec` to the single allowed method `pick_and_place`.
- [ ] Define `named_poses`, including `hold_pose` for the default place target.
- [ ] Make the provider deterministic and independent from Isaac Sim runtime state.
- [ ] Save `robot_context.json` under artifacts.
- [ ] Add a validation test that checks the generated context matches the spec shape.
