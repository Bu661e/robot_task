# llm_decision_making

`llm_decision_making/` 是机械臂抓取系统总控和决策模块。

`robot_service` 是机器人侧，部署在远程主机上·
`perception_service` 是3D数据计算侧，部署在另一个远程主机上

它的职责不是实现机器人运行时，也不是实现感知模型服务，而是：
- 读取任务
- 解析任务中的目标物体
- 向 `robot_service` 请求机器人侧启动
- 向 `robot_service` 请求机器人侧图片和深度图数据
- 向 `perception_service` 请求感知计算结果
- 基于任务和感知结果做决策
- 生成策略代码
- 向 `robot_service` 远程发送策略代码，让 robot 端执行策略

从本模块的视角看：
- `robot_service` 是黑盒
- `perception_service` 是黑盒
也就是说，`llm_decision_making` 不知道，也不在乎这两个模块内部用了什么框架、什么模型、什么控制器、什么 Isaac API。  
它只关心两件事：1. 往哪个 HTTP 接口发请求 2. 会收到什么结构化数据


## 组成

### 1. `task_loader`

负责把不同来源的任务输入整理成统一的任务内容，再交给后续解析流程。

这个模块后续支持两种入口：
- HTTP 请求
- 结合命令行参数中读取 YAML 文件内容

当前 CLI 入口约定：
- 通过 `--task-file` 指定 YAML 文件路径，默认使用 `tasks/tasks_en.yaml`
- 通过 `--task-id` 从 YAML 任务列表中选择单个任务
- 通过 `--objects-env-id` 显式提供本次运行使用的环境 id，这个参数是必填的，并且去掉首尾空白后不能为空

其中 YAML 只负责提供任务内容，`objects_env_id` 不再写在任务文件中，而是在 CLI 启动时单独提供。
如果任务 YAML 里仍然残留 `objects_env_id`，当前实现会直接报错，避免误以为旧字段仍然生效。

`task_loader` 输出是一个自定义的 `SourceTask` 结构。

内部实现上，YAML 文件读取这类与单个业务模块弱耦合的通用逻辑，应优先复用 `utils/yaml_loader.py`，避免在 `task_loader`、`policy_model` 等模块中重复实现。



### 2. `task_parser`

负责从自然语言任务中提取关键物体名。
当前实现采用 LLM 解析，由 `TaskParser` class 持有 parser 自己的模型配置、prompt 和过滤项，并复用 `utils/llm_client.py` 中的共享 LLM client 对象。
输入： 自定义 `SourceTask` 类型
输出： 自定义 `ParsedTask` 类型
中间要求 LLM 输出 JSON：`{"object_texts": [...]}`，并且 object 需要尽量使用单数形式。

### 3. `pose_transformer`

负责把相机坐标系结果转换成世界坐标系结果。

### 4. `policy_model`

负责把任务信息和感知结果交给 LLM，得到策略代码。

### 5. `policy_executor`

负责在得到 `PolicyCode` 后，通过网络协议远程调用 `robot_service`，让 robot 端执行策略代码。
这个模块需要配合 `robot_client` 使用
它不关心 robot 端内部如何解释、加载和执行策略代码。

## Client工具

### 1. `llm_client`

负责提供统一的 OpenAI-compatible LLM 调用入口，供 `task_parser` 和后续 `policy_model` 复用。

`llm_client` 的职责包括：
- 读取共享 LLM 连接配置，例如 `LLM_BASE_URL`、`LLM_API_KEY`
- 创建共享的 OpenAI-compatible client
- 通过流式 chat completion 聚合文本结果
- 默认不继承 shell 中的代理环境变量；如果确实需要继承 shell 环境，可以在 `config/llm_config.py` 中通过 `LLM_TRUST_ENV=true` 打开

当前默认通过 OpenAI-compatible 接口访问 ModelScope 推理服务，运行前需要配置 `LLM_API_KEY` 或 `MODELSCOPE_API_KEY`。

### 2. `robot_client`

负责通过 HTTP 协议访问 `robot_service`。
它属于 `utils/` 中的通用远端访问工具，而不是主流程编排模块。

`robot_client` 的功能包括：
- 启动机器人端，并发送环境参数
- 关闭机器人端
- 请求机器人端摄像头数据，包括 RGB 图、深度图、相机参数等
- 请求机器人端的可用动作 API
- 给机器人端发送控制代码

### 3. `perception_client`

负责通过 HTTP 协议访问 `perception_service`。
它属于 `utils/` 中的通用远端访问工具，而不是主流程编排模块。

`perception_client` 的功能包括：
- 将当前已经获得的 2D 信息（RGB 图、深度图、任务描述等）发送给 `perception_service`
- 接收 `perception_service` 返回的 3D 感知结果，包括目标物体的位姿、点云数据等

## 数据结构实例

### `SourceTask`
```json
{
  "task_id": "1",
  "instruction": "Pick up the tallest bottle on the table"
}
```

### CLI 运行时参数
```json
{
  "objects_env_id": "2-ycb"
}
```
说明：
- 当前 CLI 流程中，`objects_env_id` 是运行时输入，不属于 `SourceTask`
- 未来如果增加 HTTP 入口，也应把环境 id 作为独立运行时字段传入，而不是重新塞回 `SourceTask`
- 后续传给 `robot_service` 时，这个值会映射到机器人协议里的 `environment_id` 字段

### `ParsedTask`
```json
{
  "task_id": "1",
  "instruction": "Pick up the tallest bottle on the table",
  "object_texts": ["bottle"]
}
```
说明：
- `instruction` 保留原始任务文本，直接来自 `SourceTask.instruction`
- `object_texts` 只包含任务涉及的物体
- 不包含 `table` / `桌子` 等不可操纵的物体
- 例子：
  - `Pick up the tallest bottle on the table` -> `["bottle"]`
  - `Place the blue_cube on top of the red_cube` -> `["blue_cube", "red_cube"]`

 
### ...


## 典型数据流

`llm_decision_making` 的推荐链路如下：

1. 通过 `task_loader` 从 HTTP 请求或命令行参数读取 YAML 任务内容
2. 通过 CLI 必填参数 `--objects-env-id` 获取本次运行使用的环境 id
3. 在进入 `process()` 之前，基于 `objects_env_id` 创建 `robot_client`
4. 调用 `task_parser`，得到任务解析结果
5. 通过 `robot_client` 请求 `robot_service`，启动机器人端
6. 通过 `robot_client` 请求 `robot_service`，获取当前帧和机器人侧观测数据
7. 通过 `perception_client` 请求 `perception_service`，获取3D感知结果
8. 通过 `pose_transformer` 把3D感知结果转换到世界坐标系
9. 通过 `policy_model` 生成策略代码
10. 通过 `policy_executor` 远程调用 `robot_service`
11. `robot_service` 在 robot 端执行策略代码并返回执行结果

这个过程中，`llm_decision_making` 只依赖外部协议，不依赖远端实现细节。

## 当前目录中的关键文件

- `main.py`
  - 当前主流程入口
- `modules/task_loader.py`
  - 从 HTTP 请求或命令行参数读取 YAML 任务内容
- `modules/task_parser.py`
  - 基于 LLM 的任务解析
- `modules/pose_transformer.py`
  - 坐标变换
- `modules/policy_model.py`
  - LLM 策略生成
- `modules/policy_executor.py`
  - 策略执行
- `modules/schemas.py`
  - 本模块使用的数据结构定义
- `utils/yaml_loader.py`
  - 通用 YAML 文件读取工具，供任务文件和 prompt 配置文件复用
- `utils/llm_client.py`
  - 通用 OpenAI-compatible LLM 客户端，并提供共享 client 对象，供 `task_parser` 和后续 `policy_model` 复用
- `utils/robot_client.py`
  - robot HTTP 客户端工具
- `utils/perception_client.py`
  - perception HTTP 客户端工具

- configs/
  - 存放配置文件，包括远端服务地址、模型参数等
  - config/llm_config.py 定义共享 LLM 连接配置，例如 `LLM_BASE_URL`、`LLM_API_KEY` 和 `LLM_TRUST_ENV`
  - config/main_config.py 是 `main.py` 的配置文件，定义默认任务文件路径等入口参数
  - config/task_parser_config.py 是 `task_parser` 模块的配置文件，定义模型、prompt 和过滤项等 parser 自身参数
- tasks/
  - 存放任务 YAML 文件，例如 `tasks/tasks_en.yaml`

## 一句话总结

`llm_decision_making` 是一个只关心“任务、协议、数据、决策”的模块；  
`robot_service` 和 `perception_service` 对它来说都只是通过 HTTP 对接的远端黑盒服务。
