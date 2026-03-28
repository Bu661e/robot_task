# 决策和机器人接口文档

最后修改：2026-03-28-20:51

本文档定义 `llm_decision_making` 与 `robot_service` 之间的 HTTP 接口草案。

当前这版文档基于以下已确认前提：
- 接口采用多个明确端点，而不是单个通用命令端点
- 机器人侧采用 `session_id` 作为运行实例标识
- 协议面向“机器人运行能力”设计，不把 Isaac Sim 细节写死，从而兼容仿真和实体机器人
- 决策端提交任务时，会把 `task` 和 `policy_source` 一起发送给机器人侧
- 执行策略代码时，决策端会直接把 `perception_data` 放进请求体，而不是只传数据 id

## 1. 设计目标

`robot_service` 对 `llm_decision_making` 提供以下核心能力：
- 创建并管理机器人运行实例
- 提供当前观测数据
- 提供当前机器人支持的动作 API 描述
- 接收并执行由决策端提交的任务记录
- 查询同一个 session 下历史提交过的所有任务记录
- 必要时中止正在运行的任务

## 2. 基本设计原则

### 2.1 面向能力，而不是面向具体后端

接口描述的是：
- 启动一个机器人运行实例
- 获取观测
- 查询机器人能力
- 提交任务并执行策略代码

而不是：
- 启动 Isaac Sim
- 获取 Isaac Sim 相机图像
- 执行 Isaac Sim 专用脚本

也就是说，`backend_type` 可以是：
- `isaac_sim`
- `real_robot`

但接口路径本身不区分仿真和真机。

### 2.2 使用 session 作为持久化根资源

每次启动机器人端时，`robot_service` 创建一个新的运行实例，并返回 `session_id`。

当前约定 `session_id` 本身编码 `backend_type`，便于日志排查、artifact 命名以及跨后端实例区分。

一个 `session` 对应一个机器人运行实例。与这个实例直接绑定、且在整个 session 生命周期内持续有效的能力接口包括：
- `GET /sessions/{session_id}`
- `DELETE /sessions/{session_id}`
- `GET /sessions/{session_id}/robot`
- `GET /sessions/{session_id}/cameras`
- `GET /sessions/{session_id}/action-apis`

这些接口描述的是同一个持久化 session 的状态和能力，因此它们在资源语义上是同一个层级。

### 2.3 task 是 session 下的集合资源

`task` 不是 session 级别的单例上下文对象，而是挂在某个 session 下的一组持久化任务记录。

也就是说：
- 一个 session 对应一个 robot 运行实例
- 一个 session 内可以先后收到很多个 task
- 每个 task 记录都同时包含任务内容、对应的策略代码和本次执行使用的感知数据

因此，任务相关接口采用集合资源形式：
- `POST /sessions/{session_id}/tasks`
- `GET /sessions/{session_id}/tasks`
- 可选 `GET /sessions/{session_id}/tasks/{session_task_id}`
- 可选 `POST /sessions/{session_id}/tasks/{session_task_id}/cancel`

### 2.4 task 与策略代码是一体提交的

决策端不会先创建一个 task，再单独提交一段策略代码。

当前约定是：决策端通过一次 `POST /sessions/{session_id}/tasks` 请求，把以下内容一起提交给机器人侧：
- `task`
- `policy_source`
- `perception_data`

机器人侧接收到这三个核心字段后：
- 持久化保存这一条 task 记录
- 在受限执行环境中执行对应策略代码
- 通过 `task_status` 暴露该记录当前的执行状态

### 2.5 策略代码在机器人端执行

决策端不会直接持有机器人对象，也不会直接远程调用 Isaac Sim API。

决策端只负责生成并提交 `policy_source`。  
真正的 `robot` 对象由 `robot_service` 在执行环境中注入，例如：

```python
def run_policy(robot, perception_data):
    robot.pick_and_place(...)
```

这里的 `robot` 是机器人端提供的受限执行对象，而不是决策端本地对象。

### 2.6 task 执行采用异步状态模型

task 执行通常不是瞬时完成的，因此每条 task 记录都应维护独立状态。

`task_status` 建议取值：
- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

如果后续需要中止执行，可通过 task 级别的取消接口处理，而不是再单独引入另一套 execution 资源。

### 2.7 可选字段统一放入 ext

为了保证协议顶层结构稳定，所有请求体和响应体遵循以下规则：
- 第一层只放必填核心字段
- 所有可选字段统一放入 `ext`
- `ext` 固定存在；如果当前没有扩展字段，则传空对象 `{}`

## 3. 资源模型

### 3.1 Session 资源

`session` 是根资源，表示一个持久化的机器人运行实例。

建议字段：
- `session_id`
- `backend_type`
- `environment_id`
- `session_status`
- `ext`

其中：
- `session_status` 建议取值为 `starting`、`ready`、`stopped`、`error`
- 一个 session 创建成功后，通常会持续一段时间，期间可以重复查询状态、观测、能力，以及向该 session 提交多个 task

### 3.2 Session 的单例子资源

以下资源都和同一个 session 一一对应：
- `robot`
- `cameras`
- `action-apis`

它们不是独立的持久化实体集合，而是该 session 当前时刻的能力或状态视图。

### 3.3 Session 的 tasks 集合资源

`tasks` 是挂在 session 下的集合资源。

一个 task 记录表示“在某个 session 中提交过的一次任务请求”。它至少包含：
- 任务内容 `task`
- 策略代码 `policy_source`
- 执行所需的 `perception_data`
- 当前状态 `task_status`

其中：
- `perception_data` 这个字段会保留在 task 提交语义中
- 但它的正式 schema 当前还没有定稿
- 因此本阶段文档不展开 `perception_data` 的具体结构，留到第二阶段确认
- 下文示例中的 `"..."` 仅表示该字段存在，不表示它最终的数据类型是字符串

推荐的数据结构如下：

```json
{
  "session_task_id": "task_20260327153210_0001",
  "task_status": "running",
  "task": {
    "task_id": "1",
    "instruction": "Place the blue_cube on top of the red_cube",
    "object_texts": ["blue_cube", "red_cube"]
  },
  "policy_source": "def run_policy(robot, perception_data): ...",
  "perception_data": "...",
  "ext": {}
}
```

说明：
- `session_task_id` 是 `robot_service` 为该 session 内任务记录生成的唯一 id，避免和 `task.task_id` 混淆
- `task.task_id` 保留决策端原始任务 id，和 `SourceTask.task_id` / `ParsedTask.task_id` 对齐
- `GET /sessions/{session_id}/tasks` 返回的是 task 记录数组，而不是当前单个 task 上下文
- 为避免误导，以上示例未展开 `perception_data` 字段的具体内容

## 4. 接口清单

### 4.1 Session 管理接口

#### 4.1.1 创建 session

`POST /sessions`

作用：
- 创建新的机器人运行实例
- 加载场景、机器人、相机和环境配置

请求体建议：

```json
{
  "backend_type": "isaac_sim",
  "environment_id": "2-ycb",
  "ext": {}
}
```

字段说明：
- `backend_type`: 必填，当前后端类型
- `environment_id`: 必填，当前任务对应环境

响应体建议：

```json
{
  "session_id": "sess_isaac_sim_20260327153045_a1b2",
  "session_status": "ready",
  "backend_type": "isaac_sim",
  "environment_id": "2-ycb",
  "ext": {}
}
```

#### 4.1.2 查询 session 状态

`GET /sessions/{session_id}`

作用：
- 查询指定 session 当前状态

请求体建议
- 无需请求体

响应体建议

```json
{
  "session_id": "sess_isaac_sim_20260327153045_a1b2",
  "backend_type": "isaac_sim",
  "session_status": "ready",
  "environment_id": "2-ycb",
  "ext": {}
}
```

字段说明：
- `session_id`: 机器人端生成的唯一运行实例 id，推荐格式为 `sess_<backend_type>_<YYYYMMDDHHMMSS>_<rand4>`，例如 `sess_isaac_sim_20260327153045_a1b2`
- `backend_type`: 当前后端类型，取值如 `isaac_sim`、`real_robot`
- `session_status`: session 当前状态，建议取值：
  - `starting`
  - `ready`
  - `stopped`
  - `error`
- `environment_id`: 当前加载的环境标识

说明：
- 第一阶段按同步创建处理，`POST /sessions` 成功返回时默认 `session_status = ready`
- `starting` 先保留为后续扩展状态，当前阶段不要求实际使用

#### 4.1.3 关闭 session

`DELETE /sessions/{session_id}`

作用：
- 关闭指定 session
- 释放当前后端对应的运行实例、场景资源、设备资源和临时资源

请求体建议
- 无需请求体

响应体建议：

```json
{
  "session_id": "sess_isaac_sim_20260327153045_a1b2",
  "session_status": "stopped",
  "ext": {}
}
```

### 4.2 Session 状态与观测接口

#### 4.2.1 获取 robot 状态

`GET /sessions/{session_id}/robot`

作用：
- 获取当前 session 下机器人本体状态

响应体建议

```json
{
  "session_id": "sess_isaac_sim_20260327153045_a1b2",
  "timestamp": "2026-03-27T10:00:05Z",
  "robot_status": "ready",
  "ext": {}
}
```

说明：
- `robot_status` 表示当前时刻机器人本体的运行状态，建议取值：
  - `ready`
  - `busy`
  - `error`

#### 4.2.2 获取 camera 数据

`GET /sessions/{session_id}/cameras`

作用：
- 获取当前 session 下相机相关观测数据

响应体建议

```json
{
  "session_id": "sess_isaac_sim_20260327153045_a1b2",
  "timestamp": "2026-03-27T10:00:05Z",
  "cameras": [
    {
      "camera_id": "table_top",
      "rgb_image": {
        "content_type": "image/png",
        "artifact_id": "artifact_rgb_sess_isaac_sim_20260327153045_a1b2_0001"
      },
      "depth_image": {
        "content_type": "application/x-npy",
        "artifact_id": "artifact_depth_sess_isaac_sim_20260327153045_a1b2_0002"
      },
      "intrinsics": {
        "fx": 533.33,
        "fy": 533.33,
        "cx": 320.0,
        "cy": 320.0,
        "width": 640,
        "height": 640
      },
      "extrinsics": {
        "translation": [0.0, 0.0, 6.0],
        "quaternion_xyzw": [0.0, 0.7071, 0.0, 0.7071]
      },
      "ext": {
        "depth_unit": "meter",
        "depth_encoding": "npy-float32",
        "view_mode": "top_down"
      }
    },
    {
      "camera_id": "table_overview",
      "rgb_image": {
        "content_type": "image/png",
        "artifact_id": "artifact_rgb_sess_isaac_sim_20260327153045_a1b2_0003"
      },
      "depth_image": {
        "content_type": "application/x-npy",
        "artifact_id": "artifact_depth_sess_isaac_sim_20260327153045_a1b2_0004"
      },
      "intrinsics": {
        "fx": 533.33,
        "fy": 533.33,
        "cx": 320.0,
        "cy": 320.0,
        "width": 640,
        "height": 640
      },
      "extrinsics": {
        "translation": [0.0, 3.3, 3.3],
        "quaternion_xyzw": [0.1830, 0.1830, -0.6830, 0.6830]
      },
      "ext": {
        "depth_unit": "meter",
        "depth_encoding": "npy-float32",
        "view_mode": "robot_opposite_overview"
      }
    }
  ],
  "ext": {}
}
```

说明：
- 当前约定图像和深度图不直接内嵌在 JSON 中，而是通过 `artifact_id` 引用
- 决策端拿到 `artifact_id` 后，再通过单独的 artifact 下载接口获取二进制文件
- `cameras` 长期保持数组结构，即使当前只有一个相机也返回单元素数组
- 当前第一阶段默认环境会返回两个相机：`table_top` 和 `table_overview`
- `rgb_image` 为必需字段
- `depth_image` 为必需字段
- 当前第一阶段默认把深度图保存为 `float32` 的 `.npy` artifact，`content_type` 为 `application/x-npy`

### 4.3 能力描述接口

#### 4.3.1 获取动作 API 描述

`GET /sessions/{session_id}/action-apis`

作用：
- 返回当前 session 支持的动作接口描述
- 供决策端拼接 prompt 或校验策略代码

响应体建议

```json
{
  "session_id": "sess_isaac_sim_20260327153045_a1b2",
  "action_apis": [
    "robot.pick_and_place(pick_position, place_position, rotation=None)"
  ],
  "ext": {
    "action_api_version": "v20260327"
  }
}
```

说明：
- 当前约定 `action_apis` 直接使用 `str`
- 每个元素表示一个可供策略代码调用的机器人端 API 签名或简要说明
- 这样对 prompt 拼接最方便，也最接近后续 LLM 实际会看到的调用形式
- `ext.action_api_version` 使用 `vYYYYMMDD` 格式，例如 `v20260327`

### 4.4 Task 接口

#### 4.4.1 提交 task

`POST /sessions/{session_id}/tasks`

作用：
- 向指定 session 提交一条新的 task 记录
- 同时提交任务内容、策略代码和 perception 数据
- 由机器人侧持久化该记录并开始执行

请求体建议：

说明：
- 为避免把未定稿内容写死，下面的请求体示例不展开 `perception_data` 的具体结构
- 但正式请求里仍然需要携带 `perception_data` 字段

```json
{
  "task": {
    "task_id": "1",
    "instruction": "Place the blue_cube on top of the red_cube",
    "object_texts": ["blue_cube", "red_cube"]
  },
  "policy_source": "def run_policy(robot, perception_data):\n    robot.pick_and_place(...)",
  "perception_data": "...",
  "ext": {}
}
```

字段说明：
- `task`: 必填，当前任务的结构化内容
- `policy_source`: 必填，决策端生成的策略代码
- `perception_data`: 必填，当前执行所依赖的感知数据；正式 schema 留到第二阶段确认

响应体建议：

说明：
- 为避免误导，下面的响应体示例也不展开 `perception_data` 的具体结构
- `POST` 成功后是否原样回传 `perception_data`，留到第二阶段确认

```json
{
  "session_id": "sess_isaac_sim_20260327153045_a1b2",
  "session_task_id": "task_20260327153210_0001",
  "task_status": "queued",
  "task": {
    "task_id": "1",
    "instruction": "Place the blue_cube on top of the red_cube",
    "object_texts": ["blue_cube", "red_cube"]
  },
  "policy_source": "def run_policy(robot, perception_data):\n    robot.pick_and_place(...)",
  "perception_data": "...",
  "created_at": "2026-03-27T15:32:10Z",
  "updated_at": "2026-03-27T15:32:10Z",
  "ext": {}
}
```

说明：
- `POST` 成功后，代表机器人端已经接收并落库了这一条 task 记录
- `task_status` 初始建议为 `queued`
- `perception_data` 在提交语义中存在，但它在响应中的呈现形式当前不在本阶段文档中写死

#### 4.4.2 查询 session 下所有 task

`GET /sessions/{session_id}/tasks`

作用：
- 返回该 session 下已经提交过的所有 task 记录
- 每条记录都对应一组 `task`、`policy_source` 和本次执行关联的 `perception_data`

响应体建议：

说明：
- 为避免把未确认 schema 写死，下面的列表响应示例不展开 `perception_data`
- 第二阶段再确定列表接口是否直接返回 `perception_data`、返回摘要，还是仅返回引用

```json
{
  "session_id": "sess_isaac_sim_20260327153045_a1b2",
  "tasks": [
    {
      "session_task_id": "task_20260327153210_0001",
      "task_status": "succeeded",
      "task": {
        "task_id": "1",
        "instruction": "Place the blue_cube on top of the red_cube",
        "object_texts": ["blue_cube", "red_cube"]
      },
      "policy_source": "def run_policy(robot, perception_data):\n    robot.pick_and_place(...)",
      "perception_data": "...",
      "created_at": "2026-03-27T15:32:10Z",
      "updated_at": "2026-03-27T15:32:19Z",
      "ext": {}
    },
    {
      "session_task_id": "task_20260327154000_0002",
      "task_status": "running",
      "task": {
        "task_id": "2",
        "instruction": "Pick up the tallest bottle on the table",
        "object_texts": ["bottle"]
      },
      "policy_source": "def run_policy(robot, perception_data):\n    robot.pick_and_place(...)",
      "perception_data": "...",
      "created_at": "2026-03-27T15:40:00Z",
      "updated_at": "2026-03-27T15:40:03Z",
      "ext": {}
    }
  ],
  "ext": {}
}
```

说明：
- 这是当前推荐的主查询接口
- 它返回的是一个数组，表示这个 session 中发送过的所有 task record
- 如果后续任务量变大，可在 `ext` 中补充分页参数和游标

#### 4.4.3 查询单个 task 详情

`GET /sessions/{session_id}/tasks/{session_task_id}`

作用：
- 查询某一条 task 记录的完整详情
- 可用于获取更完整的执行状态、错误信息、日志摘要，以及与 `perception_data` 相关的补充信息

响应体建议：

说明：
- 详情接口未来可以返回 `perception_data` 原始结构、摘要或引用
- 但这些形式当前都还没有定稿，因此下面的示例不展开 `perception_data`

```json
{
  "session_id": "sess_isaac_sim_20260327153045_a1b2",
  "session_task_id": "task_20260327153210_0001",
  "task_status": "failed",
  "task": {
    "task_id": "1",
    "instruction": "Place the blue_cube on top of the red_cube",
    "object_texts": ["blue_cube", "red_cube"]
  },
  "policy_source": "def run_policy(robot, perception_data):\n    robot.pick_and_place(...)",
  "perception_data": "...",
  "created_at": "2026-03-27T15:32:10Z",
  "updated_at": "2026-03-27T15:32:14Z",
  "ext": {
    "error_message": "Target object not found in workspace.",
    "log_summary": [
      "robot initialized",
      "policy started",
      "target lookup failed"
    ]
  }
}
```

#### 4.4.4 中止 task

`POST /sessions/{session_id}/tasks/{session_task_id}/cancel`

作用：
- 主动中止指定 task 的执行

请求体建议：

```json
{
  "ext": {}
}
```

响应体建议：

```json
{
  "session_id": "sess_isaac_sim_20260327153045_a1b2",
  "session_task_id": "task_20260327154000_0002",
  "task_status": "cancelled",
  "ext": {}
}
```

### 4.5 Artifact 接口

#### 4.5.1 下载 artifact

`GET /artifacts/{artifact_id}`

作用：
- 下载由 `robot_service` 生成或缓存的二进制产物
- 当前主要用于下载 observation 中引用的 RGB 图、深度图等文件

返回约定：
- 成功时直接返回二进制响应体，而不是 JSON
- `Content-Type` 由具体产物决定，例如：
  - `image/png`
  - `application/octet-stream`

说明：
- `artifact_id` 由 `GET /sessions/{session_id}/cameras` 返回的图像字段提供
- `artifact_id` 推荐采用可读字符串格式：`artifact_<type>_<session_id>_<seq>`
- 如果后续需要，也可以让点云、mask、视频等产物复用同一个下载接口

## 5. 错误响应建议

所有接口建议统一错误响应结构：

```json
{
  "error_code": "NOT_FOUND",
  "message": "Requested resource not found.",
  "ext": {
    "details": {
      "resource_type": "session",
      "resource_id": "sess_isaac_sim_20260327153045_a1b2"
    }
  }
}
```

常见 `error_code` 示例：
- `INVALID_REQUEST`
- `NOT_FOUND`
- `INVALID_STATE`
- `TASK_FAILED`
- `INTERNAL_ERROR`

## 6. 当前建议的最小实现范围

如果当前目标是分阶段落地 Isaac Sim 集成，建议分两步实现。

第一阶段先打通 session、观测与 artifact 基础链路，优先实现以下 6 个接口：

Session 管理：
- `POST /sessions`
- `GET /sessions/{session_id}`
- `DELETE /sessions/{session_id}`

状态与观测：
- `GET /sessions/{session_id}/robot`
- `GET /sessions/{session_id}/cameras`

Artifact：
- `GET /artifacts/{artifact_id}`

第二阶段建议补齐能力描述和 task 执行链路：

能力描述：
- `GET /sessions/{session_id}/action-apis`

Task：
- `POST /sessions/{session_id}/tasks`
- `GET /sessions/{session_id}/tasks`
- `GET /sessions/{session_id}/tasks/{session_task_id}`
- `POST /sessions/{session_id}/tasks/{session_task_id}/cancel`

## 7. 后续待继续确认的问题

当前文档还是第一版草案，后续还需要继续确认：
- `POST /sessions/{session_id}/tasks` 中 `perception_data` 的正式 schema
- 如果后续单个 session 的 task 记录很多，`GET /sessions/{session_id}/tasks` 是否需要增加分页、筛选或裁剪视图
- task 记录是否需要额外保存执行结果字段，例如 `result_summary`、`return_value`、`generated_artifacts`
- `artifact` 资源本身的元数据结构
  例如是否需要 `content_length`、`created_at`、`artifact_type`
- 策略代码执行环境的安全约束

后续可选接口：
- `reset session`
- `health check`
