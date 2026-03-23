使用的仿真环境是 IsaacSim5.0.0，在使用 API 时候注意。

开发约定：
- 运行、测试和命令行验证时，统一使用项目根目录 `.venv` 中的 Python 环境，即 `./.venv/bin/python`，不要使用系统 Python。
- 每个模块都要单独写一个 todo list 文件。
- todo list 文件统一放在 `todos/` 目录下。
- 对应模块的任务完成后，需要在该 todo list 文件里把完成项打勾。
- todo list 文件用中文写
- 只要变量涉及项目里新定义的数据类型，就显式标注类型。
  例如 `TaskRequest`、`ParsedTask`、`FramePacket`、`PointMapPacket`、`RobotContext`、`PerceptionRequest`、`PerceptionResponse`、`CameraPerceptionResult`、`WorldPerceptionResult`、`PolicyRequest`、`PolicyCode`、`ExecutionResult`

- 代码尽可能简单，这不是工程级项目，只是个人科研类项目
