# robot_http_server 任务清单

- [x] 将 HTTP 服务模块整理到 `robot/server/http_server.py`
- [x] 保持现有 `/health`、`/capture_frame`、`/pick_and_place`、`/reset`、`/shutdown` 接口不变
- [x] 允许端口快速复用，并避免关闭时等待请求线程
