# robot_task

本仓库用于机械臂抓取任务的多模块协作开发。整体设计上包含 4 个核心模块：

- `web`：负责用户输入、任务触发与结果展示
- `llm_decision_making`：负责解析任务、组织观测、生成策略代码并调度执行
- `robot_service`：负责机器人执行、相机采集、会话管理与任务接收
- `perception_service`：负责视觉与 3D 感知计算

跨模块共享协议文档统一放在 `docs/protocols/`。


## 仓库目录说明

- `README.md`
  - 仓库级总览入口
- `docs/`
  - 仓库级共享文档目录
- `docs/protocols/`
  - 跨模块接口协议文档
- `docs/git_worktree_安排.md`
  - 多分支 + `git worktree` 开发安排说明
- `llm_decision_making/`
  - 当前已落地的决策模块代码与模块内文档

## 模块职责划分

### 1. `web`

面向用户的前端入口，负责：

- 接收用户任务输入
- 展示任务执行状态和结果
- 作为后续系统的人机交互层

### 2. `llm_decision_making`

系统总控与决策模块，负责：

- 读取和解析任务
- 请求机器人侧观测数据
- 请求感知侧计算结果
- 生成策略代码
- 把任务、策略代码和感知数据提交给 `robot_service`

它不负责实现机器人运行时，也不负责实现感知算法本身，而是通过协议与外部服务协作。

### 3. `robot_service`

机器人侧运行模块，负责：

- 创建和管理机器人运行 session
- 提供相机元数据与图像 artifact
- 对外暴露机器人能力接口
- 接收并执行决策侧提交的任务记录

### 4. `perception_service`

感知计算模块，负责：

- 接收 RGB、深度图和任务上下文
- 进行目标检测、位姿估计或 3D 感知计算
- 返回结构化感知结果供决策模块使用

## 协议与模块边界

本仓库的一个核心原则是：模块之间通过明确协议协作，而不是跨目录直接耦合内部实现。

- `llm_decision_making` 通过 HTTP 协议把 `robot_service` 和 `perception_service` 当作远端黑盒服务
- 协议文档统一维护在 `docs/protocols/`
- 修改某个模块时，应优先限制在该模块内部；如果需要跨模块变更，先同步协议边界和影响范围

当前已存在的协议文档包括：

- `docs/protocols/llm_decision_making__robot_service.md`
- `docs/protocols/llm_decision_making__perception_service.md`

## 开发方式

仓库按多分支配合 `git worktree` 的方式开发。推荐约定见 `docs/git_worktree_安排.md`：

- `main`：只用于集成与发布
- `feature/web`：前端开发
- `feature/llm-decision-making`：决策模块开发
- `feature/robot-service`：机器人服务开发
- `feature/perception-service`：感知服务开发

开发时建议注意：

- 开始编码前先确认自己当前在哪个分支
- 先确认自己当前在哪个 worktree 和工作目录
- 一个功能分支只修改本模块相关代码和必要的共享文档
- 合并前先同步最新 `main`
