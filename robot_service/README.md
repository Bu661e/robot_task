# robot_service

## 文档说明

- 早期部分计划文档、Spec 文档或调研记录是在本地开发阶段形成的，因此其中可能会提到“本地环境”和“云环境”的区别。
- 这些表述只用于说明历史背景和当时的约束，不应再被当作当前开发前提。
- 从现在开始以及后续开发，统一以云环境为准。

## 当前调研记录

### 1. Isaac Sim 的启动方式

- 当前目标后端是 Isaac Sim `5.0.0`。
- 根据官方文档，独立 Python 脚本应通过 Isaac Sim 安装目录下的 `python.sh` 启动，而不是直接使用系统 `python`。
- 推荐启动形式：

```bash
$ISAAC_SIM_ROOT/python.sh /path/to/your_script.py
```

- 这样启动的原因是：`python.sh` 会先准备 Isaac Sim 所需的 Python 路径和运行环境，再执行目标脚本。
- 独立脚本内部需要按 Isaac Sim 的 standalone 方式初始化，尤其要先创建 `SimulationApp`，再导入后续 Omniverse / Isaac Sim 相关模块。

参考文档：
- https://docs.isaacsim.omniverse.nvidia.com/5.0.0/python_scripting/manual_standalone_python.html
- https://docs.isaacsim.omniverse.nvidia.com/5.0.0/installation/install_python.html

### 2. 当前示例 `autorun.sh` 的启发

仓库当前有一个示例脚本：
- [examples/isaac_pick_place_demo/autorun.sh](examples/isaac_pick_place_demo/autorun.sh)

这个脚本已经体现出一个重要思路：
- 仓库里的任务脚本，不应该直接用系统 Python 启动
- 应该由 Isaac Sim 安装目录里的 `python.sh` 来启动

当前脚本内容核心是：

```bash
"$ISAAC_SIM_ROOT/python.sh" "$SCRIPT_DIR/main_task_armpickplace.py" "$@"
```

这对后续 `robot_service` 的架构有直接启发：
- 服务入口脚本应当由 Isaac Sim 外部 launcher 启动
- 仓库代码和 Isaac Sim 安装目录应当解耦
- `ISAAC_SIM_ROOT` 不应依赖脆弱的相对路径猜测，最好通过环境变量或明确配置传入

### 3. 当前示例存在的问题

当前这个旧示例已经整理到 `robot_service/examples/isaac_pick_place_demo/`，作为参考材料保留，但它还不能直接作为正式方案使用，至少有以下问题：

- 脚本里用 `../..` 反推出 `ISAAC_SIM_ROOT`，但在当前仓库里这个路径会落到仓库根目录，而不是 Isaac Sim 安装目录。
- 当前仓库中并不存在 `main_task_armpickplace.py`，所以这个示例脚本现在无法直接跑通。

因此，这个目录更适合作为“旧示例 / 启动方式参考”，不适合作为可直接复用的正式启动入口，也不属于当前最小服务骨架的一部分。

### 4. 对 `robot_service` 架构的直接启发

基于目前调研和当前业务前提，`robot_service` 第一阶段不需要按“多客户端 / 多 session / 多 worker”去设计。

当前已经确认的约束是：
- 只有一个客户端
- 同一时间只会打开一个 session
- 同一时间只会有一个 Isaac Sim 实例
- 同一时间只会执行一个 task
- 如果前端发来多个 task，前端会先做拦截
- 即使前端会拦截，服务端仍然要保留“拒绝第二个 session / 第二个 task”的保护逻辑

因此，当前推荐的实现不是复杂的多层服务编排，而是一个简化版的双进程结构：

1. API 进程
   使用 FastAPI，对外暴露 HTTP 接口，并维护当前唯一活动 session、当前 task、当前 worker 进程句柄和 artifact 索引。
2. Isaac worker 进程
   由 API 进程通过 Isaac Sim 的 `python.sh` 拉起，负责初始化 `SimulationApp`、加载环境、采集 observation 和执行 task。

两者之间通过简单的本地 IPC 通信即可，当前优先推荐：
- `subprocess + PTY + JSON line`

这样做的好处是：
- 保留了 API 进程和 Isaac 进程分离
- 同时避免为了未来并发场景过早引入多层 service、队列或多 worker 管理
- 更贴合当前“单客户端、单 session、单 task”的真实约束

当前云主机上的实际联调结果补充了两个实现细节：
- 在 Isaac Sim `python.sh` 下，worker stdout 会混入 Kit/Isaac 启动日志，因此读取侧不能假设每一行都是 JSON。
- 普通 pipe 形式的 stdin/stdout 在当前云主机上不够稳定，现代码已切到 PTY，并在读取 worker 事件时跳过非 JSON 行、清洗 ANSI 控制符后再解析 `WorkerEvent`。

### 5. 当前已知限制

- 当前工作环境就是云主机，默认按 Linux 主机上的长期运行服务来考虑设计、日志和排障。
- Isaac Sim 是否可用，仍然要以当前云主机上的实际安装和配置结果为准，不要只凭文档假设。
- 截至 `2026-03-28`，当前云主机已经完成以下实测：
  - `/root/isaacsim/python.sh -m robot_service.worker.entrypoint` 独立 smoke test 成功
  - 真实 `SimulationApp` 可以在云主机上启动
  - `load_environment -> get_cameras -> shutdown` 的真实 worker round-trip 已经跑通，且会产出 RGB / depth artifact
  - 当前第一阶段公开接口 `/sessions -> /robot -> /cameras -> /artifacts -> DELETE /sessions` 已在真实 Isaac Sim runtime 下跑通
  - 在当前公开接口收敛到第一阶段之前，曾用内部占位接口跑通过 `/sessions -> /robot -> /action-apis -> /tasks -> DELETE /sessions` 的真实 API 联调链路；当前对外范围仍以第一阶段协议中的 6 个接口为准

### 6. Isaac Sim 5.0 关键 API 记录

下面这些 API 是当前 `robot_service` 已经实用到、后续大概率还会继续用到的入口。优先保留官方链接，后面查资料时先看这里。

#### 6.1 standalone 启动

- 启动脚本：`$ISAAC_SIM_ROOT/python.sh`
- standalone 入口：`from isaacsim import SimulationApp`
- 当前 worker 用法：

```python
from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True})
```

官方资料：
- standalone Python 说明：https://docs.isaacsim.omniverse.nvidia.com/5.0.0/python_scripting/manual_standalone_python.html
- Python 安装/启动方式：https://docs.isaacsim.omniverse.nvidia.com/5.0.0/installation/install_python.html

#### 6.2 World / Scene

- `World` 是当前 5.x 常用的高层仿真上下文入口。
- 当前代码在重新加载环境前会先清理旧的 world，再创建新 stage 和新 world。
- 常用调用：
  - `World.clear_instance()`
  - `world = World(stage_units_in_meters=1.0)`
  - `world.scene.add_default_ground_plane()`
  - `world.reset()`

官方资料：
- Hello World 教程（`World`、`scene.add_default_ground_plane()`）：https://docs.isaacsim.omniverse.nvidia.com/5.0.0/core_api_tutorials/tutorial_core_hello_world.html
- Python API 参考（`World`、`Scene`、`GroundPlane`、`DynamicCuboid`）：https://docs.isaacsim.omniverse.nvidia.com/latest/py/source/extensions/isaacsim.core.api/docs/api.html

#### 6.3 基础环境对象

- 地面：

```python
world.scene.add_default_ground_plane()
```

- 桌子：

```python
from isaacsim.core.api.objects import FixedCuboid

world.scene.add(
    FixedCuboid(
        prim_path="/World/Furniture/Table",
        name="table",
        position=np.array([0.0, 0.0, 0.75]),
        scale=np.array([1.5, 1.5, 1.5]),
        size=1.0,
    )
)
```

- 桌面物体：

```python
from isaacsim.core.api.objects import DynamicCuboid

world.scene.add(
    DynamicCuboid(
        prim_path="/World/Tabletop/red_cube_1",
        name="red_cube_1",
        position=np.array([0.0, 0.0, 1.57]),
        scale=np.array([0.1, 0.1, 0.1]),
        size=1.0,
        color=np.array([0.62, 0.06, 0.06]),
    )
)
```

- Franka：

```python
from isaacsim.robot.manipulators.examples.franka import Franka

world.scene.add(
    Franka(
        prim_path="/World/Franka",
        name="franka",
        position=np.array([0.0, -0.6, 1.5]),
    )
)
```

- 光照：

```python
from pxr import Sdf, UsdLux

light = UsdLux.DistantLight.Define(stage, Sdf.Path("/World/KeyLight"))
light.CreateIntensityAttr(650.0)
```

官方资料：
- Core API 里的对象说明：`GroundPlane`、`DynamicCuboid` 见上面的 Python API 参考页
- `UsdLux.DistantLight.Define(...)` 的官方示例：https://docs.isaacsim.omniverse.nvidia.com/5.0.0/importer_exporter/import_mjcf.html

#### 6.4 Camera 采集 API

- 当前基础环境里有两个相机：
  - 顶视相机：位于 `(0, 0, 6.0)`，覆盖整个桌面，提供稳定的全局 RGB / depth
  - 机械臂对侧的俯视概览相机：位于 `(0, 1.8, 2.5)`，同时覆盖桌面和机械臂
  - 两个相机当前都输出 `640 x 640` 的正方形图像
  - 当前 overview 相机按 `USD/local pose` 写入固定欧拉角 `(-60, 0, -180)`，这样 Property 面板看到的值能和代码对齐
- 当前会用到的调用：
  - `camera.initialize()`
  - `camera.add_distance_to_image_plane_to_frame()`
  - `camera.get_rgba()`
  - `camera.get_current_frame(clone=True)`
  - `camera.get_intrinsics_matrix()`
  - `camera.get_world_pose(camera_axes="world")`
  - `camera.set_horizontal_aperture(...)`
  - `camera.set_focal_length(...)`

官方资料：
- Camera API 参考：https://docs.isaacsim.omniverse.nvidia.com/latest/py/source/extensions/isaacsim.sensors.camera/docs/api.html
- Rotations Utils 参考：https://docs.isaacsim.omniverse.nvidia.com/latest/py/source/extensions/isaacsim.core.utils/docs/index.html

#### 6.4.1 Camera 姿态的已踩坑记录

这次已经确认过一个很容易重复犯的错误，后面改 camera 时先看这里。

- Isaac Sim 的 `Camera.set_world_pose(..., camera_axes="world")` / `Camera.get_world_pose(..., camera_axes="world")` 用的是 Isaac 的 camera axes 约定。
- GUI 的 Property 面板里看到的 `Translate / Rotate`，显示的是 USD camera prim 本地 transform 的分解结果。
- 这两个约定不是一回事，所以“代码里写的欧拉角”和“GUI 里看到的欧拉角”不一定一致。

这次实际踩到的问题是：

- `table_overview` 目标姿态希望在 Property 面板中直接看到 `(-60, 0, -180)`。
- 如果直接写：

```python
rot_utils.euler_angles_to_quats(
    np.array([-60.0, 0.0, -180.0]),
    degrees=True,
)
```

- 由于 `euler_angles_to_quats(...)` 默认是 `extrinsic=True`，最后 GUI Property 面板会显示成 `(60, 0, -180)`，看起来像是 X 轴符号反了。

当前确认可用、且应当固定遵守的写法是：

```python
orientation = rot_utils.euler_angles_to_quats(
    np.array([-60.0, 0.0, -180.0]),
    degrees=True,
    extrinsic=False,
)

camera.set_local_pose(
    translation=np.array([0.0, 1.8, 2.5]),
    orientation=orientation,
    camera_axes="usd",
)
```

原因是：

- `extrinsic=False` 对应这里需要的 USD intrinsic XYZ 欧拉角解释。
- `camera_axes="usd"` + `set_local_pose(...)` 才是在直接给 USD camera prim 写本地姿态。
- 这样启动后，Isaac Sim GUI 的 Property 面板才能直接看到 `Rotate XYZ = (-60, 0, -180)`。

后续如果又要调整 camera 姿态，先区分清楚你要的是哪一种结果：

- 如果目标是“API 返回的世界位姿正确”，优先检查 `get_world_pose(camera_axes="world")`。
- 如果目标是“GUI Property 面板里直接显示某组欧拉角”，必须按 USD/local pose 的方式去写，不要直接套 `world` camera axes 的默认欧拉角转换。

#### 6.5 当前云主机上的实现约定

- 当前分支优先使用 `isaacsim.*` import path，不再新增 `omni.isaac.*` 写法。
- 这是因为当前云主机的 Isaac Sim `5.0.0-rc.45` 运行日志已经持续给出 `omni.isaac.*` 相关 deprecation warning，而 `isaacsim.core.api.*` 与官方 5.x 示例、安装内容是对齐的。

## 第一阶段推荐实现

### 0. 对外 API 范围

当前对外 HTTP 接口范围以协议文档 [docs/protocols/llm_decision_making__robot_service.md](/root/robot_task/docs/protocols/llm_decision_making__robot_service.md) 为准。

第一阶段只公开以下 6 个接口：

- `POST /sessions`
- `GET /sessions/{session_id}`
- `DELETE /sessions/{session_id}`
- `GET /sessions/{session_id}/robot`
- `GET /sessions/{session_id}/cameras`
- `GET /artifacts/{artifact_id}`

协议里已经定义、但属于第二阶段的接口当前不对外暴露：

- `GET /sessions/{session_id}/action-apis`
- `POST /sessions/{session_id}/tasks`
- `GET /sessions/{session_id}/tasks`
- `GET /sessions/{session_id}/tasks/{session_task_id}`
- `POST /sessions/{session_id}/tasks/{session_task_id}/cancel`

### 1. 总体结构

当前推荐的第一阶段结构是：

- 一个 FastAPI API 进程
- 一个由 API 进程按需启动的 Isaac worker 进程
- 一个活动 session

创建 session 时：
- API 收到 `POST /sessions`
- 如果当前没有活动 session，则拉起一个 Isaac worker
- worker 初始化 Isaac Sim，并根据 `environment_id` 加载桌面环境

删除 session 时：
- API 关闭当前 worker
- 当前活动 session 被清理

### 2. 状态机

#### `session_status`

- `starting`
  - API 已接受 `POST /sessions`
  - worker 正在启动，或正在加载 `environment_id`
- `ready`
  - worker 已初始化完成
  - 当前 session 可以查询状态、读取 observation
- `stopped`
  - 当前 session 已被显式关闭
  - 这是删除时的终态结果
- `error`
  - worker 启动失败、环境加载失败、进程异常退出、IPC 中断等导致当前 session 不再可用

### 3. 服务端保护逻辑

即使前端会拦截，服务端仍然保留以下保护：

- 若当前已有活动 session，则新的 `POST /sessions` 直接拒绝
- 第一阶段不对外开放 task 接口；task 相关保护逻辑留到第二阶段公开接口时一起启用

### 4. 推荐文件结构

当前已实现的第一阶段最小结构如下：

```text
robot_service/
  README.md
  pyproject.toml

  api/
    app.py
    manager.py

  worker/
    entrypoint.py
    environment.py
    queries.py
    task_runner.py
    tabletop_layouts/
      __init__.py
      models.py
      default.py

  common/
    schemas.py
    messages.py

  runtime/
    settings.py
    logging_config.py
    paths.py
    ids.py

  tests/
    test_runtime.py
    test_schemas.py
    test_manager.py
    test_app.py
    test_worker_units.py
```

### 5. 各文件职责

#### `api/app.py`

负责：
- 创建 FastAPI app
- 注册全部 HTTP 路由
- 在路由中调用 `RobotServiceManager`

当前阶段建议把全部路由都先放在这个文件里，而不是拆成多个 route 文件。

#### `api/manager.py`

这是第一阶段核心文件。

建议只保留一个主类：
- `RobotServiceManager`

它直接维护：
- `active_session`
- `current_task`
- `task_history`
- `worker_handle`
- `artifact_index`

它负责：
- session 创建、查询、删除
- 与 worker 的命令发送和事件接收
- session 状态更新

#### `worker/entrypoint.py`

负责：
- 初始化日志
- 创建 `SimulationApp`
- 启动 worker 命令循环

注意：
- 这个文件要最先初始化 Isaac Sim
- 其他 worker 文件不应重复初始化 `SimulationApp`

#### `worker/environment.py`

负责：
- 清理并重建基础环境
  - ground
  - light
  - table
  - franka
  - table_top camera
  - table_overview camera
- 根据 `environment_id` 调用对应桌面环境文件并加载桌面物体
- 采集两个相机的 RGB / depth，并把它们落成 artifact

当前代码里已先实现：
- 接收并保存 `environment_id`
- 在没有 Isaac Sim Python 模块时回退到占位模式
- 在真实 Isaac Sim runtime 下创建基础环境：
  - `ground`
  - `light`
  - `1.5m x 1.5m x 1.5m` 立方体桌子
  - 放在桌子一侧中间的 Franka
  - 离地 `6m` 的顶视相机
  - 位于机械臂对侧、同时覆盖桌面和机械臂的概览相机
- 默认桌面环境 `env-default`
  - `2` 个红色方块
  - `2` 个蓝色方块
  - 尺寸约 `10cm`
  - 随机且避免明显重叠的桌面摆放
  - 使用更深的红蓝配色，避免在较弱光照下和桌面颜色过于接近

#### `worker/tabletop_layouts/`

负责：
- 把“桌面环境”从“基础环境”里拆出来
- 每个 `environment_id` 对应一个独立文件或构建函数

当前代码里：
- `default.py` 实现了 `env-default`
- 后续新增桌面环境时，优先继续按这个目录扩展，而不是把所有环境硬塞回 `environment.py`

#### `worker/queries.py`

负责：
- 获取 robot 状态
- 获取 camera 元数据和 artifact 引用

当前代码里：
- `robot_status` 返回占位 `ready`
- `cameras` 会返回真实双相机的：
  - `rgb_image`
  - `depth_image`
  - intrinsics
  - extrinsics

#### `worker/task_runner.py`

这是第二阶段预留文件。

负责：
- 执行 task
- 跟踪当前 task 是否在运行
- 支持取消当前 task

当前不作为第一阶段公开 API 的一部分；真实机器人执行逻辑留到第二阶段开放时再继续补齐。

#### `common/schemas.py`

负责：
- HTTP 请求/响应模型
- session / task / artifact 结构
- cameras / robot 结构

#### `common/messages.py`

负责：
- API 进程和 worker 进程之间的内部消息结构
- 例如命令：
  - `load_environment`
  - `get_robot_status`
  - `get_cameras`
  - `get_action_apis`
  - `run_task`
  - `cancel_task`
  - `shutdown`
- 以及事件：
  - `worker_ready`
  - `environment_loaded`
  - `task_started`
  - `task_succeeded`
  - `task_failed`
  - `task_cancelled`
  - `artifact_created`
  - `worker_error`

#### `runtime/settings.py`

负责读取运行配置，例如：
- `ISAAC_SIM_ROOT`
- `ROBOT_SERVICE_HOST`
- `ROBOT_SERVICE_PORT`
- `RUNS_DIR`
- `LOG_LEVEL`

#### `runtime/logging_config.py`

负责统一初始化日志，要求：
- API 和 worker 进程复用一致的日志格式
- 同时输出终端和文件

#### `runtime/paths.py`

负责：
- `runs/` 目录
- session 目录
- artifact 文件路径

#### `runtime/ids.py`

负责：
- `session_id`
- `session_task_id`
- `artifact_id`

### 6. 当前明确去掉的复杂设计

在当前约束下，以下设计先不做：

- 多客户端
- 多活动 session
- 多个 Isaac worker
- 同一 session 下的 task 队列
- 多层 service 拆分
- 多个 route 文件
- 额外的数据库、消息队列、任务队列系统

如果未来业务前提变化，再从当前最小结构逐步扩展。

## 当前实现限制

目前代码已经实现：
- FastAPI API 骨架
- 第一阶段公开接口：session / robot / cameras / artifacts
- `environment_id` 从 HTTP 接口传到 worker
- PTY + JSON line 的 worker IPC
- 基础环境与桌面环境拆分
- 默认基础环境：`ground`、`light`、`table`、`franka`、`table_top camera`、`table_overview camera`
- 默认桌面环境：`env-default` 的 `2` 红 `2` 蓝方块
- 真实相机 artifact 输出：
  - RGB -> `image/png`
  - depth -> `application/x-npy`
- 本地可运行的单元测试
- `2026-03-28` 在当前云主机上的真实 worker smoke test
- `2026-03-28` 在当前云主机上的真实第一阶段 API smoke test

目前还没有实现：
- 除 `env-default` 之外的其他桌面环境
- 第二阶段的动作 API 描述接口
- 第二阶段的 task 执行、查询和取消接口
