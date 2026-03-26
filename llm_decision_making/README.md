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
  
输出是一个自定义的 `TaskDescription` 结构。



### 2. `task_parser`

负责从自然语言任务中提取关键物体名。
输入： 自定义 `TaskDescription` 类型
输出： 自定义 `ParsedTask` 类型

### 3. `robot_client`

负责通过 HTTP 协议访问 `robot_service`。

robot_client的功能包括：
- 启动机器人端，并发送环境参数
- 关闭机器人端
- 请求机器人端摄像头数据，包括RGB图、深度图、相机参数等
- 请求机器人端的可用动作API
- 给机器人端发送控制代码。

### 4. `perception_client`

负责通过 HTTP 协议访问 `perception_service`。

perception_client的功能包括：
- 将当前已经获得的2D信息（RGB图、深度图、任务描述等）发送给 `perception_service`
- 接收 `perception_service` 返回的3D感知结果，包括目标物体的位姿、点云数据等。


### 5. `pose_transformer`

负责把相机坐标系结果转换成世界坐标系结果。

### 6. `policy_model`

负责把任务信息和感知结果交给 LLM，得到策略代码。

### 7. `policy_executor`

负责在得到 `PolicyCode` 后，通过网络协议远程调用 `robot_service`，让 robot 端执行策略代码。
这个模块需要配合 `robot_client` 使用
它不关心 robot 端内部如何解释、加载和执行策略代码。

## 数据结构实例

### `TaskDescription`
```json
{
  "task_id": "1",
  "objects_env_id": "2-ycb",
  "instruction": "Pick up the tallest bottle on the table"
}
```

### `ParsedTask`
```json
{
  "task_id": "1",
  "object_texts": ["bottle"]
}
```
说明：
- `object_texts` 只包含任务涉及的物体
- 不包含 `table` / `桌子` 等不可操纵的物体
- 例子：
  - `Pick up the tallest bottle on the table` -> `["bottle"]`
  - `Place the blue_cube on top of the red_cube` -> `["blue_cube", "red_cube"]`

 
### ...


## 典型数据流

`llm_decision_making` 的推荐链路如下：

1. 通过 `task_loader` 从 HTTP 请求或命令行参数读取 YAML 任务内容
2. 调用 `task_parser`，得到任务解析结果
3. 通过 `robot_client` 请求 `robot_service`，启动机器人端
4. 通过 `robot_client` 请求 `robot_service`，获取当前帧和机器人侧观测数据
5. 通过 `perception_client` 请求 `perception_service`，获取3D感知结果
6. 通过 `pose_transformer` 把3D感知结果转换到世界坐标系
7. 通过 `policy_model` 生成策略代码
8. 通过 `policy_executor` 远程调用 `robot_service`
9. `robot_service` 在 robot 端执行策略代码并返回执行结果

这个过程中，`llm_decision_making` 只依赖外部协议，不依赖远端实现细节。

## 当前目录中的关键文件

- `main.py`
  - 当前主流程入口
- `modules/task_loader.py`
  - 从 HTTP 请求或命令行参数读取 YAML 任务内容
- `modules/task_parser.py`
  - 任务解析
- `modules/robot_client.py`
  - robot HTTP 客户端
- `modules/perception_client.py`
  - perception HTTP 客户端
- `modules/pose_transformer.py`
  - 坐标变换
- `modules/policy_model.py`
  - LLM 策略生成
- `modules/policy_executor.py`
  - 策略执行
- `modules/schemas.py`
  - 本模块使用的数据结构定义

- configs/
  - 存放配置文件，包括远端服务地址、模型参数等
  - config/task_parser_config.py 是 `task_parser` 模块的配置文件，定义了任务解析相关的参数和选项

## 一句话总结

`llm_decision_making` 是一个只关心“任务、协议、数据、决策”的模块；  
`robot_service` 和 `perception_service` 对它来说都只是通过 HTTP 对接的远端黑盒服务。
