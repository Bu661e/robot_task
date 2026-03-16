# 机械臂抓取系统代码生成规格
版本：v4
日期：2026-03-16
## 1. 目标
做一个最小闭环：
- 输入：自然语言任务
- 本地：机器人侧采集 RGB / Depth，生成 point map，调用机器人控制器
- 远程：一次调用感知服务，服务内部按 `SAM3 -> SAM3D` 顺序执行
- LLM：根据任务、感知结果、机器人 API 生成 Python 代码
- 执行：统一调用 `robot.pick_and_place(...)`
这个文档只做三件事：
1. 固定模块
2. 固定接口
3. 固定 JSON 格式
---
## 2. 固定模块
### 2.1 本地模块
### M1. `task_parser`
作用：
- 只提取任务里涉及的物体名
- 不解析动作
- 不解析空间关系
- 不解析目标选择逻辑
- 默认忽略 `table` / `桌子`
- 物体角色和空间关系由 LLM 根据 `instruction` 自行理解
输入：
- `TaskRequest`
输出：
- `ParsedTask`
### M2. `robot_bridge`
作用：
- 从机器人运行时获取 RGB、Depth、相机参数
- 生成 `point_map`
- 提供 `robot` 控制对象
- 当前阶段主要对接仿真机器人，后续可替换为真实机器人
输入：
- 无
输出：
- `FramePacket`
- `PointMapPacket`
### M3. `robot_config_provider`
作用：
- 提供预先设定好的机器人上下文配置
- 不从机器人运行时读取
输入：
- 无
输出：
- `RobotContext`
### M4. `perception_client`
作用：
- 负责从本地调用远程感知服务
- 负责把本地数据封装成 `PerceptionRequest`
- 发送 RGB 文件、point map 文件、物体名
- 接收远程 HTTP 响应
- 将 HTTP 响应中的 mask 文件保存到本地主机
- 将远程返回结果整理成相机坐标系下的 `CameraPerceptionResult`
输入：
- `ParsedTask`
- `FramePacket`
- `PointMapPacket`
输出：
- `CameraPerceptionResult`
说明：
- 正常情况下输出 `CameraPerceptionResult`
- 如果远程服务返回失败响应，则当前链路立即终止，不再进入 `pose_transformer`、`policy_model`、`policy_executor`
### M5. `pose_transformer`
作用：
- 把相机坐标系下的感知结果转换到世界坐标系
- 坐标变换基于 `FramePacket.camera.extrinsics_camera_to_world`
输入：
- `CameraPerceptionResult`
- `FramePacket`
输出：
- `WorldPerceptionResult`
### M6. `policy_model`
作用：
- LLM 根据任务、感知结果、机器人 API 生成 Python 代码
- 物体筛选、空间关系理解、目标选择都由 LLM 根据 `instruction` 和 `WorldPerceptionResult` 完成
输入：
- `PolicyRequest`
输出：
- `PolicyCode`
### M7. `policy_executor`
作用：
- 在受控环境中执行代码
- 调用 `robot.pick_and_place(...)`
输入：
- `PolicyCode`
- `robot`
- `RobotContext`
- `WorldPerceptionResult`
输出：
- `ExecutionResult`
运行约束：
- 只执行 Python
- 入口函数固定为 `run(robot, perception, named_poses)`
- 代码抛出异常时，需转换为失败的 `ExecutionResult`
### 2.2 远程服务模块
### S1. `perception_service`
作用：
- 一次调用完成整条感知链
- 服务内部固定顺序执行：
  1. `SAM3` 做开放词汇分割
  2. `SAM3D` 基于分割结果做 3D 恢复
- 对外只暴露一个接口，但内部是两阶段流水
内部流程：
- 第一步：读取 `object_texts`
- 第二步：对每个物体名调用 `SAM3`，得到该类物体的候选 masks
- 第三步：汇总所有 masks，并保留 `label -> mask` 对应关系
- 第三步补充：如果没有分割出任何 mask，则直接返回失败的 `PerceptionHTTPResponse`，不再调用 `SAM3D`
- 第四步：将 RGB、point map、masks 送入 `SAM3D`
- 第五步：对每个 mask 恢复 3D 信息，生成相机坐标系下的 objects
- 第六步：在 HTTP 响应中返回每个 object 对应的 mask 文件
- 第七步：返回 `PerceptionHTTPResponse`
要求：
- 服务必须保留 `SAM3` 的中间结果，便于调试
- 服务返回的每个 object 必须带 `label`
- 服务返回的每个 object 必须带 `source_mask_id`
- `SAM3D` 的输入必须和 `SAM3` 输出实例一一对应
- HTTP 响应必须包含每个 object 对应的 mask 文件内容
- 如果 `SAM3` 没有产出任何 mask，服务必须返回失败响应，并终止本次调用
输入：
- `PerceptionRequest`
输出：
- `PerceptionHTTPResponse`
---
## 3. 机器人动作 API
当前只开放一个动作接口给 LLM：
```python
robot.pick_and_place(pick_position, place_position, rotation=None)
```
参数约束：
- `pick_position`: `[x, y, z]` 抓取参考点的世界坐标
- `place_position`: `[x, y, z]` 放置点的世界坐标
- `rotation`: `[w, x, y, z]` 或 `None`  抓取时的末端姿态（四元数）
- 单位统一为米
约束：
- LLM 不允许直接控制关节
- LLM 不允许直接访问机器人底层对象，或仿真 / 真机 SDK 底层对象
- 所有任务最终都要翻译成一次 `pick_and_place(...)`
---
## 4. 坐标与单位
原始感知数据使用相机坐标系：
- `FramePacket`: `Camera`
- `PointMapPacket`: `Camera`
- `CameraPerceptionResult`: `Camera`
执行与控制使用世界坐标系：
- `WorldPerceptionResult`: `World`
- 长度单位：`m`
- 旋转：四元数 `[w, x, y, z]`

说明：
- `robot_bridge` 需要提供相机到世界坐标系的外参
- `pose_transformer` 负责把相机坐标系结果转换到世界坐标系结果
- `frame_id` 表示一次采样帧的唯一标识，例如 `frame_0001`
- `coordinate_frame` 用来表示当前数据所在坐标系，取值固定为 `camera` 或 `world`
---
## 5. 模块连接
固定链路：
```text
TaskRequest
  -> task_parser
  -> ParsedTask

robot_bridge
  -> FramePacket
  -> PointMapPacket
  -> robot

robot_config_provider
  -> RobotContext

ParsedTask + FramePacket + PointMapPacket
  -> perception_client
  -> PerceptionRequest
  -> perception_service
  -> PerceptionHTTPResponse
  -> if success=false: terminate
  -> perception_client
  -> CameraPerceptionResult

CameraPerceptionResult + FramePacket
  -> pose_transformer
  -> WorldPerceptionResult

TaskRequest + ParsedTask + WorldPerceptionResult + RobotContext
  -> policy_model
  -> PolicyCode

PolicyCode + robot + RobotContext + WorldPerceptionResult
  -> policy_executor
  -> ExecutionResult
```
---
## 6. JSON 接口
### 6.1 `TaskRequest`
```json
{
  "task_id": "task_0001",
  "instruction": "Pick up the tallest bottle on the table"
}
```
### 6.2 `ParsedTask`
```json
{
  "task_id": "task_0001",
  "object_texts": ["bottle"]
}
```
说明：
- `object_texts` 只包含任务涉及的物体
- 不包含 `table` / `桌子`
- 例子：
  - `Pick up the tallest bottle on the table` -> `["bottle"]`
  - `Place the blue_cube on top of the red_cube` -> `["blue_cube", "red_cube"]`
### 6.3 `FramePacket`
```json
{
  "frame_id": "frame_0001",
  "timestamp": "2026-03-16T09:00:00Z",
  "coordinate_frame": "camera",
  "rgb_path": "data/frame_0001_rgb.png",
  "depth_path": "data/frame_0001_depth.npy",
  "camera": {
    "intrinsics": [[fx, 0, cx], [0, fy, cy], [0, 0, 1]],
    "extrinsics_camera_to_world": [[...], [...], [...], [...]]
  }
}
```
### 6.4 `PointMapPacket`
```json
{
  "frame_id": "frame_0001",
  "timestamp": "2026-03-16T09:00:00Z",
  "coordinate_frame": "camera",
  "point_map_path": "data/frame_0001_pointmap.npy",
  "point_format": "xyz_camera"
}
```
说明：
- `point_map[x, y] = [X, Y, Z]`
- 坐标在相机坐标系下
- 如果 point map 由深度图在本地自行反投影得到，则默认定义为相机坐标系
- 如果当前实现使用 Isaac Sim Camera API 的 `get_pointcloud()` 且保持默认参数，则结果默认是世界坐标系
- 本项目统一约定 `PointMapPacket` 使用相机坐标系
### 6.5 `PerceptionRequest`
这是 `perception_client` 发送给远程 `perception_service` 的 HTTP 请求体。
```json
{
  "frame_id": "frame_0001",
  "timestamp": "2026-03-16T09:00:00Z",
  "coordinate_frame": "camera",
  "rgb_file": {
    "file_name": "frame_0001_rgb.png",
    "encoding": "base64_png",
    "content": "iVBORw0KGgoAAA..."
  },
  "point_map_file": {
    "file_name": "frame_0001_pointmap.npy",
    "encoding": "base64_npy",
    "content": "k05VTVBZA..."
  },
  "object_texts": ["bottle"]
}
```
### 6.6 `PerceptionHTTPResponse`
这是远程 `perception_service` 返回给 `perception_client` 的 HTTP 响应体。
```json
{
  "success": true,
  "frame_id": "frame_0001",
  "timestamp": "2026-03-16T09:00:00Z",
  "coordinate_frame": "camera",
  "objects": [
    {
      "instance_id": "obj_001",
      "label": "bottle",
      "source_mask_id": "mask_001",
      "mask_file": {
        "file_name": "mask_001.png",
        "encoding": "base64_png",
        "content": "iVBORw0KGgoAAA..."
      },
      "3d_info": {
        "translation_m": [0.12, -0.03, 0.85],
        "rotation_wxyz": [1.0, 0.0, 0.0, 0.0],
        "scale_m": [0.06, 0.06, 0.24],
        "extra": {
          "sam3_score": 0.93
        }
      },
      ...
    }
  ]
}
```
说明：
- 这是远程服务的原始 HTTP 响应体
- `success=true` 表示感知链正常完成
- `objects` 是数组，可能包含 0 个、1 个或多个物体，具体数量取决于当前图像内容和任务中的关键物体
- 每个 object 都直接带自己的 mask 文件内容
- `objects[i]` 和其中的 `mask_file` 是一一对应的
- `perception_client` 负责把这些 mask 文件保存到本地主机
- `3d_info` 的固定必选字段是：
  - `translation_m`
  - `rotation_wxyz`
  - `scale_m`
- `3d_info.extra` 是可选扩展字段

失败响应示例：
```json
{
  "success": false,
  "frame_id": "frame_0001",
  "timestamp": "2026-03-16T09:00:00Z",
  "coordinate_frame": "camera",
  "error": {
    "code": "SAM3_NO_MASK",
    "message": "SAM3 did not produce any mask for the requested object_texts"
  }
}
```
失败规则：
- 当 `SAM3` 没有分割出任何 mask 时，远程服务必须返回失败响应
- 一旦 `success=false`，本次任务后续不再执行 `pose_transformer`、`policy_model`、`policy_executor`
### 6.7 `CameraPerceptionResult`
这是 `perception_client` 接收到 `PerceptionHTTPResponse` 后，在本地主机保存 mask 文件并整理字段后得到的输出。
```json
{
  "frame_id": "frame_0001",
  "timestamp": "2026-03-16T09:00:00Z",
  "coordinate_frame": "camera",
  "masks": [
    {
      "label": "bottle",
      "mask_id": "mask_001",
      "score": 0.93,
      "bbox_xyxy": [120, 80, 180, 220],
      "mask_path": "data/masks/mask_001.png"
    }
  ],
  "objects": [
    {
      "instance_id": "obj_001",
      "label": "bottle",
      "source_mask_id": "mask_001",
      "3d_info": {
        "translation_m": [0.12, -0.03, 0.85],
        "rotation_wxyz": [1.0, 0.0, 0.0, 0.0],
        "scale_m": [0.06, 0.06, 0.24],
        "extra": {
          "sam3_score": 0.93
        }
      },
      ...
    }
  ]
}
```
说明：
- 这是 `perception_client` 处理 HTTP 响应后得到的本地 JSON
- `mask_path` 是本地主机上的路径，不是远程主机路径
- `objects` 是数组，可能包含多个物体
- `objects` 是服务内部 `SAM3D` 输出的结果
- 这里的坐标仍然在相机坐标系下
- `masks` 主要用于调试，可选返回
- `masks[].score`、`masks[].bbox_xyxy` 是可选字段；如果远程服务未返回，则本地可以省略
- `3d_info` 的固定必选字段是：
  - `translation_m`
  - `rotation_wxyz`
  - `scale_m`
- `3d_info.extra` 是可选扩展字段
### 6.8 `WorldPerceptionResult`
```json
{
  "frame_id": "frame_0001",
  "timestamp": "2026-03-16T09:00:00Z",
  "coordinate_frame": "world",
  "objects": [
    {
      "instance_id": "obj_001",
      "label": "bottle",
      "source_mask_id": "mask_001",
      "3d_info": {
        "translation_m": [0.42, 0.11, 0.15],
        "rotation_wxyz": [1.0, 0.0, 0.0, 0.0],
        "scale_m": [0.06, 0.06, 0.24],
        "extra": {
          "sam3_score": 0.93
        }
      }
    }
  ]
}
```
说明：
- 这是 `pose_transformer` 输出
- `objects` 是数组，可能包含多个物体
- 坐标已经在世界坐标系下
- `LLM` 主要使用这个结果
- `3d_info` 的固定必选字段是：
  - `translation_m`
  - `rotation_wxyz`
  - `scale_m`
- `3d_info.extra` 是可选扩展字段
### 6.9 `RobotContext`
```json
{
  "coordinate_frame": "world",
  "robot_name": "franka",
  "api_spec": {
    "methods": [
      {
        "name": "pick_and_place",
        "args": ["pick_position", "place_position", "rotation"]
      }
    ]
  },
  "named_poses": {
    "hold_pose": [0.5, 0.0, 0.4]
  }
}
```
说明：
- 由系统预先设定，并由 `robot_config_provider` 提供
- 不从机器人运行时中读取
- `api_spec` 是给 `LLM` 的可调用接口说明
- `named_poses` 是可选字段，用于提供预定义位置
- `named_poses["hold_pose"]` 表示默认放置位置，仅在任务没有明确放置目标时使用
### 6.10 `PolicyRequest`
```json
{
  "task": {
    "task_id": "task_0001",
    "instruction": "Pick up the tallest bottle on the table",
    "object_texts": ["bottle"]
  },
  "perception": {
    "frame_id": "frame_0001",
    "timestamp": "2026-03-16T09:00:00Z",
    "coordinate_frame": "world",
    "objects": [
      {
        "instance_id": "obj_001",
        "label": "bottle",
        "source_mask_id": "mask_001",
        "3d_info": {
          "translation_m": [0.42, 0.11, 0.15],
          "rotation_wxyz": [1.0, 0.0, 0.0, 0.0],
          "scale_m": [0.06, 0.06, 0.24],
          "extra": {
            "sam3_score": 0.93
          }
        },
        ...
      }
    ]
  },
  "robot_context": {
    "coordinate_frame": "world",
    "robot_name": "franka",
    "api_spec": {
      "methods": [
        {
          "name": "pick_and_place",
          "args": ["pick_position", "place_position", "rotation"]
        }
      ]
    },
    "named_poses": {
      "hold_pose": [0.5, 0.0, 0.4]
    }
  }
}
```
### 6.11 `PolicyCode`
```json
{
  "language": "python",
  "entrypoint": "run",
  "code": "def run(robot, perception, named_poses):\n    bottles = [o for o in perception['objects'] if o['label'] == 'bottle']\n    target = max(bottles, key=lambda o: o['3d_info']['translation_m'][2] + o['3d_info']['scale_m'][2] / 2)\n    robot.pick_and_place(target['3d_info']['translation_m'], named_poses['hold_pose'], target['3d_info']['rotation_wxyz'])"
}
```
说明：
- `language` 当前固定为 `python`
- `entrypoint` 当前固定为 `run`
- 运行时签名固定为 `run(robot, perception, named_poses)`
- 只允许使用执行器提供的入参和基础 Python 能力
### 6.12 `ExecutionResult`
```json
{
  "task_id": "task_0001",
  "success": true,
  "selected_object_id": "obj_001",
  "executed_api": "pick_and_place",
  "message": "done"
}
```
---
## 7. 远程服务形式
远程感知服务按客户端-服务器方式调用，但每个任务本地只调用一次。
推荐形式：
- 协议：HTTP JSON
- 图片/点图：直接上传文件内容
- 返回：标准 JSON
### 7.1 Perception
请求：
```http
POST /perception/infer
```
请求体：
- `PerceptionRequest`
返回：
- `PerceptionHTTPResponse`
服务内部执行顺序：
```text
for label in object_texts:
  SAM3(rgb, label) -> masks[label]

merge all masks
if no mask:
  return PerceptionHTTPResponse(success=false)

SAM3D(rgb, point_map, masks) -> camera_objects

pack HTTP response:
  camera_objects + mask_files -> PerceptionHTTPResponse

perception_client:
  if success=true:
    save mask files to local paths
    build CameraPerceptionResult
```
---
## 8. 统一执行规则
### 8.0 感知失败时
- 如果远程 `perception_service` 返回 `success=false`，则本次任务立即结束
- 不再执行 `pose_transformer`、`policy_model`、`policy_executor`
- 失败原因以 `PerceptionHTTPResponse.error` 为准
### 8.1 用户只要求“拿起”
统一转成：
```text
pick_position = target.3d_info.translation_m
place_position = named_poses["hold_pose"]
```
说明：
- 当前 v1 中，`target.3d_info.translation_m` 被视为抓取参考点
- 后续如果接入 grasp planner，可将该参考点替换为更精确的抓取点
### 8.2 用户要求“放到另一个物体上”
可由 LLM 参考以下方式计算：
```text
place_x = target_object.3d_info.translation_m[0]
place_y = target_object.3d_info.translation_m[1]
place_z = target_object.3d_info.translation_m[2] + target_object.3d_info.scale_m[2] / 2 + source_object.3d_info.scale_m[2] / 2 + 0.03
```
其中 `0.03` 是安全间隙。
---
## 9. 推荐产物
```text
res/{start_time}/{task_id}/
  data/
    frame_0001_rgb.png
    frame_0001_depth.npy
    frame_0001_pointmap.npy
    masks/
      mask_001.png
      mask_002.png
  artifacts/
    task_request.json
    parsed_task.json
    frame_packet.json
    point_map_packet.json
    robot_context.json
    perception_request.json
    perception_http_response.json
    camera_perception_result.json
    world_perception_result.json
    policy_request.json
    policy_code.json
    policy_code.py
    execution_result.json
```
说明：
- `perception_http_response.json` 始终建议保留
- 如果 `PerceptionHTTPResponse.success=false`，则 `camera_perception_result.json`、`world_perception_result.json`、`policy_request.json`、`policy_code.json`、`policy_code.py`、`execution_result.json` 可以不生成
---
## 10. 最小闭环
```text
1. 用户输入自然语言任务
2. `task_parser` 提取任务中的关键物体，得到 `ParsedTask`
3. `robot_bridge` 从机器人运行时读取 RGB、Depth、相机参数，并生成 `PointMapPacket`
4. `perception_client` 组装 `PerceptionRequest`，调用远程 `perception_service`
5. 远程服务内部按 `SAM3 -> SAM3D` 顺序执行，返回 `PerceptionHTTPResponse`
6. 如果 `PerceptionHTTPResponse.success=false`，则本次流程立即结束
7. `perception_client` 将 HTTP 响应整理为 `CameraPerceptionResult`
8. `pose_transformer` 将相机坐标系结果转换为 `WorldPerceptionResult`
9. `policy_model` 将任务、`WorldPerceptionResult` 和 `RobotContext` 交给 LLM，生成 Python 代码
10. `policy_executor` 执行代码，并调用 `robot.pick_and_place(...)`
```
