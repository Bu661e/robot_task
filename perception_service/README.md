# perception_service

`perception_service/` 用于承载远程感知服务代码。

按照 [CodeGenSpec.md](/Users/haitong/Code_ws/robot_task/llm_decision_making/CodeGenSpec.md) 当前约定，这个模块对应远程服务模块 `S1 perception_service`，职责是：

- 接收 `PerceptionRequest`
- 按 `SAM3 -> SAM3D` 顺序执行感知链
- 返回 `PerceptionResponse`

当前先创建独立目录，后续再补服务入口、推理流水线和调试产物落盘逻辑。
