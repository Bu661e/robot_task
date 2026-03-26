# llm_decision_making_remove_robot_code 任务清单

- [x] 删除 `llm_decision_making/modules/robot_bridge.py`
- [x] 删除 `llm_decision_making/modules/robot_config_provider.py`
- [x] 删除 `llm_decision_making/main.py` 中直接启动和控制 robot 的逻辑
- [x] 删除 `schemas.py` 与 `policy_executor.py` 中的 `RobotContext` 占位接口
- [x] 保留 `llm_decision_making` 作为独立决策模块的最小入口
