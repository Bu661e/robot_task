# robot_task

本仓库包含 4 个核心模块：`web` 负责用户输入与结果展示；`llm_decision_making` 负责解析指令、结合观测生成策略代码；`robot_service` 负责接收策略、控制机器人并采集摄像头数据；`perception_service` 负责视觉与 3D 感知计算。跨模块协议文档统一放在 `docs/protocols/`。

`docs/` 用于存放仓库级共享文档，包括跨模块接口协议和 `git worktree` 开发安排说明。
