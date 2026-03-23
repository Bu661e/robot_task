# Isaac Sim Worker 设计说明

## 1. 设计目标

worker 是一个长期存活的机器人侧进程。

它和主进程解耦，主进程只通过 `modules/robot_bridge.py` 和本地 HTTP 协议访问它。

当前固定约束：

- Isaac Sim 版本：5.0.0
- 监听地址：`127.0.0.1`
- v1 通信协议：标准库 HTTP
- v1 LLM 可见机器人 API：只保留 `pick_and_place`

## 2. 生命周期

### 2.1 启动流程

1. 主进程创建本轮输出目录
2. 主进程调用 `modules.robot_bridge.start_worker(...)`
3. `robot/autorun.sh` 使用 Isaac Sim Python 启动 `robot.worker_main`
4. worker 初始化 `RobotWorkerRuntime`
5. worker 尝试初始化 `SimulationApp`、`World`、基础环境和桌面环境
6. worker 启动 HTTP 服务
7. 主进程轮询 `/health`，ready 后认为 worker 可用

### 2.2 运行期间

- `capture_frame`：采集 RGB / Depth / point map，并返回 `FramePacket` / `PointMapPacket`
- `pick_and_place`：执行一次原子抓放
- `reset`：重置当前场景

### 2.3 退出流程

1. 主进程调用 `/shutdown`
2. worker HTTP 服务退出
3. worker 关闭 `SimulationApp`
4. 主进程回收子进程并关闭日志文件句柄

## 3. 场景分层

### 3.1 基础环境

基础环境始终固定，应该包含：

- Franka 机械臂
- 桌面
- 相机
- 灯光
- 必要地面或世界基础对象

当前代码位置：

- `robot/scenes.py`
- `BaseEnvironmentBuilder.build(world)`

当前状态：

- 只保留了 `add_default_ground_plane()`
- 其余对象还未补齐

### 3.2 桌面环境

桌面环境只负责“桌面上摆什么物体、如何摆”。

当前约定：

- 启动 worker 时传入 `scene_id`
- 一轮任务内 `scene_id` 固定不变
- 不同桌面环境通过 scene builder 分开实现

当前代码位置：

- `robot/scenes.py`
- `get_desktop_scene_builder(scene_id)`

当前状态：

- 只提供 `default_scene` 占位实现

## 4. HTTP 协议

### `GET /health`

返回示例：

```json
{
  "ready": false,
  "scene_id": "default_scene",
  "base_environment_loaded": false,
  "desktop_scene_loaded": false,
  "frame_output_dir": "res/2026-0323-130000/robot_frames",
  "error": "..."
}
```

含义：

- `ready`: 当前 worker 是否完成初始化
- `error`: 初始化失败时的错误信息

### `POST /capture_frame`

当前预期返回：

```json
{
  "success": true,
  "frame_packet": {...},
  "point_map_packet": {...}
}
```

当前状态：

- 接口路径与返回结构已固定
- Isaac Sim 采帧逻辑尚未实现

### `POST /pick_and_place`

请求示例：

```json
{
  "pick_position": [0.42, 0.11, 0.15],
  "place_position": [0.50, 0.00, 0.40],
  "rotation": [1.0, 0.0, 0.0, 0.0]
}
```

当前状态：

- 路径已固定
- worker 端控制器映射尚未实现

### `POST /reset`

当前实现：

- 如果 runtime 已 ready，会直接调 `world.reset()`

### `POST /shutdown`

当前实现：

- 触发 HTTP server 停止
- 之后由 `worker_main.py` 在退出阶段关闭 runtime

## 5. 文件落盘策略

worker 不通过 HTTP 回传大文件内容。

固定策略：

- 主进程在启动 worker 时传入本轮 `session_dir`
- worker 在 `session_dir/robot_frames/` 下写采样文件
- 返回 JSON 中只带文件路径

后续 `capture_frame` 实现完成后，建议文件名固定为：

- `{frame_id}_rgb.png`
- `{frame_id}_depth.npy`
- `{frame_id}_point_map.npy`

## 6. `RobotProxy` 边界

主进程代码生成阶段只能看到这个接口：

```python
robot.pick_and_place(pick_position, place_position, rotation=None)
```

这条边界不要破坏：

- 不要让 LLM 直接访问 Isaac Sim 对象
- 不要把生成出的 Python 代码发给 worker 执行
- 不要在 v1 额外开放 move/open/close 等更底层原语

## 7. 当前实现完成度

### 已完成

- 主进程侧 `robot_bridge` 启动/轮询/关闭骨架
- worker 入口、runtime、HTTP server、scene builder 文件结构
- 本地 HTTP 协议路径与返回结构
- 日志写入路径约定

### 未完成

- Isaac Sim 5.0.0 API 实测
- Franka 与相机的真实加载
- 桌面物体场景配置
- RGB / Depth / point map 采样
- `pick_and_place` 控制链路

## 8. 下个 session 必做事项

1. 在正确的 Isaac Sim 5.0.0 环境中运行 `robot/autorun.sh`
2. 先修通 `/health`
3. 再实现 `capture_frame`
4. 再实现 `pick_and_place`
5. 最后再打开 `main.py` 里的 robot worker 运行测试
