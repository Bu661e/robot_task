# 主进程与机器人进程设计说明

## 目标

将系统拆成两个部分：

- 主进程：负责任务编排、远程感知调用、大模型代码生成、策略执行
- 机器人进程：负责机器人侧的场景 / 设备状态、相机采集、机械臂控制

这样可以让主进程与具体机器人后端解耦，后端既可以是仿真机器人，也可以是真实机器人。

## 机器人进程的两种形态

机器人进程可以有两种实现：

- 仿真机器人进程：例如 Isaac Sim
- 真实机器人进程：例如真实相机 + 真实机械臂控制系统

两者对主进程应尽量暴露同一套能力接口，例如：

- 启动 / 初始化
- 采集当前帧
- 执行 `pick_and_place`
- 重置
- 关闭

当前阶段，我们先主要讨论仿真机器人进程，因为当前系统开发和验证主要基于 Isaac Sim。

## 推荐架构

### 1. 主进程

`llm_decision_making/main.py` 运行在项目自己的普通 Python 环境中。

职责：

- 加载任务文件
- 调用 `M1 task_parser`
- 调用远程感知服务
- 构造 `WorldPerceptionResult`
- 调用大模型生成 `PolicyCode`
- 在 `policy_executor` 中执行生成的代码

### 2. 机器人进程

机器人进程负责维护机器人侧运行时。

当前主要实现形态：

- 一个长期存活的 Isaac Sim worker 进程
- 使用 Isaac Sim 自带的 Python 环境，例如通过 `python.sh` 启动

未来可替换形态：

- 一个长期存活的真实机器人 worker 进程
- 内部对接真实相机、标定数据和真实机械臂控制接口

### 3. 当前重点：仿真机器人进程

在当前阶段，仿真机器人进程的职责包括：

- 启动 `SimulationApp`
- 加载桌面、机械臂、相机和场景物体
- 在整轮任务期间保持场景存活
- 采集 RGB、Depth、相机参数和 point map
- 在仿真中执行真实的机械臂控制逻辑

## 为什么机器人进程要长期存活

不要只为了采一帧图像而启动 Isaac Sim，然后立刻退出。

原因：

- 感知之后，系统还要在同一个机器人侧状态里执行策略
- 如果进程退出，场景状态或设备状态就丢失了
- 机械臂、物体摆放、控制器上下文都要重新初始化

所以更合理的设计是：

- 机器人进程只启动一次
- 在任务执行期间一直保持运行
- 等整轮任务结束后再关闭

这条原则对仿真机器人和真实机器人都成立；当前阶段主要对应 Isaac Sim。

## 环境使用策略

整个项目不需要全部运行在 Isaac Sim 的 Python 环境中。

推荐拆分方式：

- 主进程：普通 Python 环境
- 仿真机器人进程：Isaac Sim Python 环境

后续切到真实机器人时，也保持同样的思路：

- 主进程：普通 Python 环境
- 真实机器人进程：真实设备运行时环境

这样可以避免依赖冲突，也能把机器人侧特有代码集中在 `robot_bridge` 和动作执行部分。

## 一个重要约束

一个已经运行中的 Python 进程，不能中途切换解释器变成 Isaac Sim 的 Python 环境。

所以当前仿真方案的正确做法是：

- 主进程使用 `subprocess.Popen(...)`
- 启动一个新的 Isaac Sim worker 子进程
- 两个进程之间通过本地通信交互

未来切到真实机器人时，也建议保持类似结构：

- 主进程负责总控
- 机器人进程负责机器人侧运行时

## 通信方式

主进程和机器人进程之间，建议通过本地 RPC / IPC 通信，例如：

- 本地 socket
- 本地 HTTP
- ZeroMQ
- 其他简单的本地消息通道

具体用哪一种，后面可以再定，整体架构不依赖某一种特定实现。

## 关键设计：不要把代码字符串发给机器人进程执行

大模型生成出来的策略代码，不建议直接发给机器人进程执行。

更好的方式是：

- 主进程负责执行生成的 Python 代码
- 提供给代码的 `robot` 不是底层机器人对象
- 这个 `robot` 是一个代理对象
- 代理对象把 `robot.pick_and_place(...)` 转成结构化动作命令
- 机器人进程接收到动作命令后，再调用真实控制器或仿真控制器执行

这样比“远程执行任意 Python 字符串”更清晰，也更安全。

## 推荐执行流程

1. `llm_decision_making/main.py` 启动机器人 worker。
2. worker 加载机器人侧运行时，并保持存活。
3. `llm_decision_making/main.py` 请求 worker 采集当前帧。
4. worker 返回或保存 RGB、Depth、相机内外参和 point map。
5. `llm_decision_making/main.py` 继续执行感知、LLM 规划等步骤。
6. 主进程中的 `policy_executor` 执行：
   - `run(robot_proxy, perception, named_poses)`
7. 在生成代码内部调用：
   - `robot.pick_and_place(...)`
   实际上调用的是代理对象。
8. 代理对象把结构化动作命令发给机器人 worker。
9. worker 在机器人侧执行真实动作。
10. worker 把执行结果返回给主进程。

## RobotProxy 的作用

生成代码看到的机器人接口，仍然保持规范要求的形式：

```python
robot.pick_and_place(pick_position, place_position, rotation=None)
```

但这里的 `robot` 不是底层机器人对象，而是主进程里的 `RobotProxy`。

示意代码：

```python
class RobotProxy:
    def __init__(self, client):
        self.client = client

    def pick_and_place(self, pick_position, place_position, rotation=None):
        return self.client.send({
            "cmd": "pick_and_place",
            "pick_position": pick_position,
            "place_position": place_position,
            "rotation": rotation,
        })
```

## 机器人进程应该做什么

机器人进程内部应该提供一些结构化命令处理，例如：

- 初始化运行时
- 采集当前帧
- 执行 `pick_and_place`
- 重置
- 关闭

在执行动作时，机器人进程接收的只是结构化动作参数，而不是策略代码字符串。

例如：

```json
{
  "cmd": "pick_and_place",
  "pick_position": [0.42, 0.11, 0.15],
  "place_position": [0.50, 0.00, 0.40],
  "rotation": [1.0, 0.0, 0.0, 0.0]
}
```

## 与当前模块划分的对应关系

- `M2 robot_bridge`：主进程向机器人进程请求采集数据
- `M6 policy_model`：主进程调用大模型生成 Python 代码
- `M7 policy_executor`：主进程执行 Python 代码
- 机器人动作执行：通过 `RobotProxy` 转发给机器人进程

## 后续切换到真实机器人时的意义

如果现在就按“主进程 + 机器人进程”的方式设计，那么后续从仿真切换到真实机器人时：

- 主进程基本不需要重写
- `M1`、`M4`、`M5`、`M6`、`M7` 的主体逻辑可以保持不变
- 主要替换的是机器人进程内部实现
- `RobotProxy` 和主进程看到的机器人 API 可以尽量保持不变

也就是说，主进程不需要关心后端到底是仿真机器人还是真实机器人，只需要依赖统一的机器人侧接口。

## 实际结论

当前最推荐的实现路径是：

1. 保持 `llm_decision_making/main.py` 作为系统总控
2. 后续增加一个长期存活的机器人 worker
3. 当前优先实现仿真机器人 worker
4. 再补一个本地通信层
5. 再补一个 `RobotProxy`
6. 策略代码继续放在主进程执行
7. 机器人状态和真实控制留在 worker 进程中

这个方案既符合当前 `CodeGenSpec.md` 的整体设计，也为后续切换到真实机器人预留了清晰的替换路径。
