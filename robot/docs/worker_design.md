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
6. worker 后台启动 HTTP 服务
7. worker 主线程持续执行仿真循环
8. 主进程轮询 `/health`，ready 后认为 worker 可用

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

- `robot/config.py`
- `robot/scenes/base_environment.py`

当前状态：

- 已包含：
  - 地面
  - 简洁桌子几何体
  - Franka
  - 顶视相机
  - 基础灯光
- 所有手动可调参数集中放在 `robot/config.py`
- Franka 初始姿态已改为可配置的“拍照姿态”
- 顶视相机已增加“中央工作区”配置，用于让拍照视野优先覆盖桌面中间区域

### 3.2 桌面环境

桌面环境只负责“桌面上摆什么物体、如何摆”。

当前约定：

- 启动 worker 时传入 `scene_id`
- 一轮任务内 `scene_id` 固定不变
- 不同桌面环境通过 scene builder 分开实现

当前代码位置：

- `robot/scenes/__init__.py`
- `get_desktop_scene_builder(scene_id)`
- `robot/scenes/desktop_scene_blocks.py`
- `robot/scenes/desktop_scene_ycb.py`

当前状态：

- 已提供：
  - `default_scene`
    - `blocks_scene` 的兼容别名
  - `blocks_scene`
    - 4 个固定红蓝方块
  - `ycb_scene`
    - 4 个 YCB physics 物体

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
- 已实现主线程采集 RGB / Depth / point map
- 返回 `FramePacket.camera.intrinsic`
- 返回 `FramePacket.camera.extrinsics_camera_to_world`
- 文件固定落到 `session_dir/robot_frames/`

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

- 如果 runtime 已 ready，会先登记 reset 请求，再由主仿真线程执行 `world.reset()`
- reset 后会重新进入短暂稳定阶段，之后 `/health.ready` 再恢复为 `true`
- 这样可以避免后台 HTTP 线程直接操作 Isaac `World`，减少 reset 后姿态不生效的问题

### `POST /shutdown`

当前实现：

- 设置 runtime 停止标记
- 触发 HTTP server 停止
- `worker_main.py` 最终关闭 runtime 和 `SimulationApp`

## 5. 文件落盘策略

worker 不通过 HTTP 回传大文件内容。

固定策略：

- 主进程在启动 worker 时传入本轮 `session_dir`
- worker 在 `session_dir/robot_frames/` 下写采样文件
- 返回 JSON 中只带文件路径

当前 `capture_frame` 文件名约定为：

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
- worker 入口、runtime、HTTP server、主循环结构
- 本地 HTTP 协议路径与返回结构
- 日志写入路径约定
- 基础环境：
  - 桌子
  - Franka
  - 顶视相机
  - 灯光
- 两个桌面场景：
  - `blocks_scene`
  - `ycb_scene`
- `robot/config.py` 统一手动配置入口

### 未完成

- `pick_and_place` 控制器接入与实测
- `pick_and_place` 控制链路

## 8. 下个 session 必做事项

1. 在正确的 Isaac Sim 5.0.0 环境中运行 `robot/autorun.sh`
2. 先验证 `/health` 与 `/capture_frame`
3. 再人工检查 `blocks_scene` 与 `ycb_scene` 的布局
4. 再实现 `pick_and_place`
5. 最后再打开 `main.py` 里的 robot worker 运行测试
