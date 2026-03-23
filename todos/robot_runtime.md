# robot_runtime 任务清单

- [x] 重构 `robot/runtime/worker_runtime.py` 的 ready 逻辑
- [x] 增加主线程仿真循环
- [x] 支持场景稳定帧后再将 `/health.ready` 置为 `true`
- [x] 调整 `reset` 与 `shutdown` 行为适配新主循环
- [x] 按 Isaac Sim 5.0.0 要求修正 `SimulationApp` 初始化前后的导入顺序
- [x] 在 worker 启动与 `/reset` 后重新应用 Franka 拍照姿态
- [x] 将 `/reset` 改为主线程执行，避免后台 HTTP 线程直接操作 `World`
