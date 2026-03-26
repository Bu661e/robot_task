# robot_client 任务清单

- [x] 在 `llm_decision_making/modules/` 下新增 `robot_client.py`
- [x] 将 `robot_client` 约束为纯 HTTP 客户端
- [x] 提供 `health`、`capture_frame`、`pick_and_place` 三个基础接口
- [x] 保持 `robot_client` 不依赖 `robot_service` 内部实现
