# robot_bridge 任务清单

- [x] 创建模块文件 `modules/robot_bridge.py`
- [x] 固定模块输出类型引用
- [x] 确定主进程与 Isaac Sim worker 通信方式为本地 HTTP
- [x] 确定场景选择方式为启动时 `scene_id`
- [x] 确定 LLM 侧只暴露 `pick_and_place`
- [x] 实现 worker 启动、健康检查、关闭与 `RobotProxy` 桥接骨架
- [x] 新增 `robot/` 下的 worker 骨架与交接文档
- [ ] 在 Isaac Sim 5.0.0 环境中实测 `/health`
- [ ] 在 Isaac Sim 5.0.0 环境中实测 `capture_frame`
- [ ] 在 Isaac Sim 5.0.0 环境中实测 `pick_and_place`
