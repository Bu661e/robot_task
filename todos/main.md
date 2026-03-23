# main 任务清单

- [x] 创建主入口文件 `main.py`
- [x] 添加命令行参数 `--instruction`
- [x] 添加命令行参数 `--task-file`
- [x] 添加命令行参数 `--task-index`
- [x] 添加命令行参数 `--output-dir`
- [x] 添加命令行参数 `--scene-id`
- [x] 添加命令行参数 `--enable-robot-worker`
- [x] 添加命令行参数 `--robot-headless`
- [x] 实现 task loader，将命令行输入统一转换为 `TaskRequest`
- [x] 将 task loader 拆分到 `utils/task_loader.py`
- [x] 接入 `task_loader -> task_parser` 主链路
- [x] 接入 robot worker 生命周期骨架与采帧请求入口
- [ ] 实现完整主流程编排
- [ ] 在 Isaac Sim 5.0.0 环境中验证与机器人模块的真实通信
