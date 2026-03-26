# Isaac Sim Worker 测试清单

当前 session **不执行** 以下测试。  
这些测试是给下一个具备 Isaac Sim 5.0.0 环境的 session 直接照着做的。

## 1. worker 启动与 `/health` 就绪测试

### 前置条件

- 机器已安装 Isaac Sim 5.0.0
- `robot/autorun.sh` 能找到 Isaac Sim 的 `python.sh`
- 项目代码处于当前实现版本

### 执行步骤

1. 用 Isaac Sim 环境运行 `robot/autorun.sh --scene-id default_scene --session-dir <输出目录>`
2. 观察 worker 是否持续运行
3. 用 `curl http://127.0.0.1:8899/health` 请求健康检查

### 预期结果

- worker 进程不应立刻退出
- `/health` 返回 200
- 返回体里的 `ready` 为 `true`
- `base_environment_loaded` 和 `desktop_scene_loaded` 为 `true`

### 失败时优先排查

- `robot_worker.stderr.log`
- Isaac Sim 5.0.0 import 是否成功
- `robot/autorun.sh` 是否找到正确的 `python.sh`
- `scene_id` 是否存在对应 builder

## 2. `capture_frame` 文件落盘与 schema 完整性测试

### 前置条件

- `/health` 已 ready
- 基础环境中的相机已真正创建完成

### 执行步骤

1. 调 `POST /capture_frame`
2. 检查返回 JSON 中是否包含 `frame_packet` 和 `point_map_packet`
3. 检查返回路径上的文件是否真实存在
4. 检查 `FramePacket` / `PointMapPacket` 字段是否符合 `llm_decision_making/modules/schemas.py`

### 预期结果

- 生成 RGB PNG 文件
- 生成 Depth NPY 文件
- 生成 point map NPY 文件
- `coordinate_frame` 固定为 `camera`
- `camera.intrinsic` 和 `extrinsics_camera_to_world` 有效

### 失败时优先排查

- 相机 prim 是否真正加载
- RGB / Depth 数据读取 API 是否适配 Isaac Sim 5.0.0
- point map 的计算与写盘逻辑
- 返回 JSON 是否和 `schemas.py` 一致

## 3. 不同 `scene_id` 对应不同桌面环境测试

### 前置条件

- 至少实现两个桌面场景 builder

### 执行步骤

1. 分别启动 `scene_id=A` 和 `scene_id=B`
2. 对每个场景执行一次 `/health` 和 `/capture_frame`
3. 对比两次采集结果中的桌面物体差异

### 预期结果

- 基础环境不变
- 桌面物体配置发生变化
- 两个场景都能返回合法采帧结果

### 失败时优先排查

- scene builder 是否真的分层
- 是否把基础环境误写进桌面场景 builder
- `scene_id` 路由是否正确

## 4. `RobotProxy -> /pick_and_place` 抓放链路测试

### 前置条件

- Franka 机械臂与控制器已接入
- 桌面上存在可抓取物体

### 执行步骤

1. 在主进程侧创建 `RobotProxy`
2. 调 `robot.pick_and_place(...)`
3. 观察 worker 是否收到 `POST /pick_and_place`
4. 观察仿真中机械臂是否完成动作

### 预期结果

- HTTP 请求成功
- worker 无异常
- 机械臂完成一次抓放
- 返回 JSON 中 `success=true`

### 失败时优先排查

- `RobotProxy` 请求参数格式
- worker 对控制器的参数映射
- Franka 控制器初始化是否完成
- 抓取点/放置点坐标是否使用世界坐标系

## 5. 主进程退出后的 worker 清理测试

### 前置条件

- worker 能正常启动

### 执行步骤

1. 主进程启动 worker
2. 正常结束一次任务，确认会调用 `close_worker()`
3. 再模拟中途异常，确认 `finally` 分支也会关闭 worker
4. 检查端口和子进程是否已释放

### 预期结果

- worker 不残留僵尸进程
- 8899 端口可再次启动复用
- `robot_worker.stdout.log` 和 `robot_worker.stderr.log` 正常关闭

### 失败时优先排查

- `/shutdown` 是否真正触发了 HTTP server 退出
- `close_worker()` 的 wait/kill 逻辑
- 主进程异常路径是否漏掉 finally 清理
