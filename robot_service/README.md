# robot_service

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
- [examples/isaac_pick_place_demo/autorun.sh](/Users/haitong/Code_ws/robot_task/.worktrees/feature-robot-service/robot_service/examples/isaac_pick_place_demo/autorun.sh)

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
- `subprocess + stdin/stdout JSON line`

这样做的好处是：
- 保留了 API 进程和 Isaac 进程分离
- 同时避免为了未来并发场景过早引入多层 service、队列或多 worker 管理
- 更贴合当前“单客户端、单 session、单 task”的真实约束

### 5. 当前已知限制

- 当前开发环境不是云主机，也不是 Linux 环境。
- 当前工作区没有 Isaac Sim `5.0.0` 运行环境。
- 因此，上述结论目前属于架构和启动方式调研结论，不代表已经完成真实启动验证或真实联调测试。

## 第一阶段推荐实现

### 1. 总体结构

当前推荐的第一阶段结构是：

- 一个 FastAPI API 进程
- 一个由 API 进程按需启动的 Isaac worker 进程
- 一个活动 session
- 一个运行中的 task

创建 session 时：
- API 收到 `POST /sessions`
- 如果当前没有活动 session，则拉起一个 Isaac worker
- worker 初始化 Isaac Sim，并根据 `environment_id` 加载桌面环境

删除 session 时：
- API 关闭当前 worker
- 当前活动 session 被清理

提交 task 时：
- 只有当 session 已经 `ready` 且当前没有运行中 task 时才允许提交
- worker 接收 task 并执行
- 当前阶段 `run_task` 仍是占位实现：接口和状态机会走通，但不会执行真实机械臂策略

### 2. 状态机

#### `session_status`

- `starting`
  - API 已接受 `POST /sessions`
  - worker 正在启动，或正在加载 `environment_id`
- `ready`
  - worker 已初始化完成
  - 当前 session 可以查询状态、读取 observation、提交 task
- `stopped`
  - 当前 session 已被显式关闭
  - 这是删除时的终态结果
- `error`
  - worker 启动失败、环境加载失败、进程异常退出、IPC 中断等导致当前 session 不再可用

#### `task_status`

- `queued`
  - API 已接受 task 请求，但 worker 还未正式开始执行
- `running`
  - worker 已开始执行 task
- `succeeded`
  - task 执行成功结束
- `failed`
  - task 执行失败，但不一定代表整个 session 已损坏
- `cancelled`
  - task 被显式取消

### 3. 服务端保护逻辑

即使前端会拦截，服务端仍然保留以下保护：

- 若当前已有活动 session，则新的 `POST /sessions` 直接拒绝
- 若当前 session 不在 `ready`，则不允许提交 task
- 若当前已有 `queued` 或 `running` task，则新的 `POST /tasks` 直接拒绝
- 若当前有运行中 task，则 `DELETE /sessions/{session_id}` 直接拒绝
- 当前阶段暂不支持取消运行中的 task；`cancel` 只保留接口位置，真实中止能力待云主机联调时补上

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
- task 创建、查询、取消
- 与 worker 的命令发送和事件接收
- session/task 状态更新

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
- 加载固定基础环境
  - 机械臂
  - 桌子
  - 光照
  - 相机
- 根据 `environment_id` 加载桌面物体环境

当前代码里已先实现：
- 接收并保存 `environment_id`
- 建立默认场景占位：`ground`、`light`、`block`

真实 Isaac Sim 场景搭建和不同 `environment_id` 对应的桌面内容，留到云主机环境补上。

#### `worker/queries.py`

负责：
- 获取 robot 状态
- 获取 camera 元数据和 artifact 引用
- 获取 action API 描述

当前代码里：
- `robot_status` 返回占位 `ready`
- `action_apis` 返回占位 `pick_and_place` 签名
- `cameras` 先返回空数组和占位说明

#### `worker/task_runner.py`

负责：
- 执行 task
- 跟踪当前 task 是否在运行
- 支持取消当前 task

当前阶段不做 task 队列。
当前代码里也还没有接真实机器人执行逻辑，只先返回占位成功结果，保证 API、状态机和 IPC 能先跑通。

#### `common/schemas.py`

负责：
- HTTP 请求/响应模型
- session / task / artifact 结构
- cameras / robot / action APIs 结构

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
- 单 session / 单 task 状态机
- `environment_id` 从 HTTP 接口传到 worker
- worker 默认环境占位
- 本地可运行的单元测试

目前还没有实现：
- 云主机 / Linux 上的真实启动验证
- Isaac Sim `5.0.0` 下的真实 `SimulationApp` 联调
- 真实机械臂、桌子、光照、相机的完整场景创建
- 不同 `environment_id` 对应不同桌面物体布局
- 真实相机图像 artifact 输出
- 运行中 task 的真实取消
