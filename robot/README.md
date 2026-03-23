# robot 子系统说明

## 目标

`robot/` 目录存放机器人侧全部代码与文档。

这里的机器人侧是一个独立于 `main.py` 的 Isaac Sim worker 进程，职责是：

- 启动 Isaac Sim 5.0.0 运行时
- 加载固定基础环境与可切换的桌面场景
- 提供本地 HTTP 接口给 `modules/robot_bridge.py`
- 后续负责相机采帧与 `pick_and_place` 动作执行

主进程与机器人侧边界固定如下：

- 主进程环境：项目根目录 `.venv`
- worker 环境：Isaac Sim 自带 Python，由 `robot/autorun.sh` 启动
- 主进程不直接 import Isaac Sim API
- LLM 不直接接触 Isaac Sim 底层对象，只能通过 `RobotProxy.pick_and_place(...)` 间接调用

## 当前仓库状态

- `task_parser` 已打通，并能通过配置好的 LLM 返回 `ParsedTask`
- `main.py` 已能执行到 `M1 task_parser`
- `robot_bridge` 已完成主进程桥接骨架
- `robot/` 已补齐 worker 骨架、基础环境和两个桌面场景
- `robot/config.py` 已作为 robot 侧统一手动配置入口
- 当前已在 Isaac Sim 5.0.0 环境中实测通过 `/health` 与基础场景加载
- `capture_frame` 和 `pick_and_place` 仍是待补完的 Isaac 侧实现点

## 目录说明

- `config.py`
  - robot 侧统一手动配置入口，集中管理资产路径、桌子尺寸、Franka 位姿、Franka 拍照姿态、相机位姿、顶视相机中央工作区和桌面物体布局
- `autorun.sh`
  - Isaac Sim worker 启动入口
- `worker_main.py`
  - worker 进程入口，负责参数解析、runtime 初始化、后台 HTTP 服务启动和主线程仿真循环
- `server/`
  - `server/http_server.py`，本地 HTTP 协议与服务实现
- `runtime/`
  - `runtime/worker_runtime.py`，Isaac Sim runtime 生命周期、主循环、采帧与动作接口占位实现
- `scenes/`
  - 场景 builder 注册入口、基础环境 builder 和桌面场景 builder
- `docs/worker_design.md`
  - 详细设计与接口约定
- `docs/test_checklist.md`
  - 后续在 Isaac 环境中必须执行的测试清单

## 当前代码已经做了什么

- 在主进程侧增加了 `modules/robot_bridge.py`
- `robot_bridge` 已支持：
  - 启动 worker 子进程
  - 轮询 `/health`
  - 请求 `/capture_frame`
  - 请求 `/reset`
  - 请求 `/shutdown`
  - 创建 `RobotProxy`
- worker HTTP 协议已固定为：
  - `GET /health`
  - `POST /capture_frame`
  - `POST /pick_and_place`
  - `POST /reset`
  - `POST /shutdown`
- worker 会先绑定 HTTP 端口，再初始化 Isaac Sim
  - 如果 `8899` 已被旧 worker 占用，会立刻报错并提示用 `/health` 或 `/shutdown` 排查
- worker 主线程现在会持续跑 Isaac Sim 仿真循环
  - 非 headless 模式下窗口可以保持渲染
  - `/health.ready` 会在基础环境和桌面场景加载完成、并经过少量稳定帧后变为 `true`
- Franka 现在支持可配置的拍照姿态
  - worker 启动和 `/reset` 后都会自动回到该姿态
- 顶视相机现在支持“中央工作区”配置
  - 当前会优先对准桌面中央工作区，而不是尽量拍满整张桌子
- 当前支持的 `scene_id`：
  - `default_scene`
    - `blocks_scene` 的兼容别名
  - `blocks_scene`
    - 4 个固定红蓝方块
  - `ycb_scene`
    - 4 个来自 `/root/Downloads/YCB/Axis_Aligned_Physics/` 的 YCB 物体
- worker 日志会落到每轮输出目录下：
  - `robot_worker.stdout.log`
  - `robot_worker.stderr.log`
- `main.py` 已增加：
  - `--scene-id`
  - `--enable-robot-worker`
  - `--robot-headless`
- 当前默认 **不会** 自动启动 worker。
  - 这是为了让非 Isaac 环境下仍能继续调试主进程。
  - 真正进入 M2 时，需要显式加 `--enable-robot-worker`。

## 当前还没完成什么

- 没有在 Isaac Sim 5.0.0 环境中实机验证当前场景代码
- `capture_frame` 还没有真正写出 RGB / Depth / point map
- `pick_and_place` 还没有真正接到 Franka 控制器

## 下个 session 建议顺序

1. 在装好 Isaac Sim 5.0.0 的机器上先跑 `robot/autorun.sh`
2. 用 `curl` 验证 `/health`
3. 先直接肉眼检查 `blocks_scene` 和 `ycb_scene` 的布局是否符合预期
4. 再补齐相机采帧
5. 补齐 `pick_and_place`
6. 再把 `main.py` 的 robot worker 开关真正打开做链路测试
