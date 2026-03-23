# robot_worker_main 任务清单

- [x] 重构 `robot/worker_main.py` 为后台 HTTP + 主线程仿真循环
- [x] 补充线程关闭与 runtime 清理逻辑
- [x] 初始化失败时在终端打印提示，并优化 Ctrl+C 的优雅退出
- [x] 在启动 Isaac Sim 前先绑定 HTTP 端口，避免端口占用时慢失败
