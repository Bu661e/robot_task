# 工作区说明

本工作区按三个**完全独立**的模块组织：

- `robot_service/`
- `llm_decision_making/`
- `perception_service/`

开发时必须把这三个目录视为三个独立系统，而不是一个可以随意互相 import 的大工程。

## 核心约束

三者之间**只允许通过 HTTP 协议传输数据**。

这条约束是整个工作区最重要的边界：

- 不允许 `llm_decision_making` 直接调用 `robot_service` 的内部运行时对象
- 不允许 `llm_decision_making` 直接调用 `perception_service` 的内部推理代码
- 不允许 `robot_service` 直接 import `perception_service`
- 不允许 `perception_service` 直接 import `robot_service`

如果后续需要共享字段定义、请求结构或响应结构，应该通过明确的 HTTP 协议文档、JSON schema，或单独抽出的协议层处理，而不是直接跨模块耦合业务实现。

## 模块说明

### 1. `robot_service/`

这是机器人侧模块。

职责：

- 维护 Isaac Sim 5.0.0 运行时
- 维护场景、相机、机械臂和桌面物体状态
- 提供采帧能力
- 提供机器人动作执行能力
- 对外暴露机器人 HTTP 服务

它的定位是“机器人后端”。

后续它可以运行在远程主机上，也可以替换成真实机器人后端；但无论后端怎么变，对 `llm_decision_making` 暴露的都应该是稳定的 HTTP 接口，而不是内部 Python 对象。

### 2. `llm_decision_making/`

这是主流程和决策模块。

职责：

- 读取任务
- 做任务解析
- 通过 HTTP 调用 `robot_service`
- 通过 HTTP 调用 `perception_service`
- 整理感知结果
- 做坐标变换
- 调用 LLM 生成策略代码
- 在本地执行策略代码
- 通过受控 `robot_service` 接口触发动作

它的定位是“系统总控 + LLM 决策层”。

这个模块不负责维护 Isaac Sim，不负责感知模型推理，也不应该持有机器人底层对象。

### 3. `perception_service/`

这是远程感知服务模块。

职责：

- 接收来自 `llm_decision_making` 的感知请求
- 执行整条感知流水线
- 负责 `SAM3 -> SAM3D` 之类的视觉推理过程
- 返回标准化感知结果

它的定位是“独立远程视觉服务”。

这个模块不负责任务规划，不负责执行机器人动作，也不应该依赖机器人运行时。

## 模块关系

推荐的数据流如下：

1. `llm_decision_making` 通过 HTTP 请求 `robot_service` 采集当前帧
2. `llm_decision_making` 通过 HTTP 请求 `perception_service` 做感知
3. `llm_decision_making` 基于感知结果生成并执行策略
4. `llm_decision_making` 通过 HTTP 请求 `robot_service` 执行动作

也就是说：

- `robot_service` 只负责“机器人侧状态与动作”
- `perception_service` 只负责“感知”
- `llm_decision_making` 只负责“编排、理解、决策和执行调度”

## 目录调整原则

后续新增代码时，必须先判断它属于哪个模块：

- 跟 Isaac Sim、场景、相机、机械臂控制强相关的代码，放 `robot_service/`
- 跟任务解析、感知结果整理、LLM 决策、策略执行相关的代码，放 `llm_decision_making/`
- 跟视觉模型推理、mask、3D 恢复、感知服务接口相关的代码，放 `perception_service/`

如果某段代码同时想依赖两个模块的内部实现，通常说明边界已经坏了，需要先重构接口，而不是继续堆代码。
