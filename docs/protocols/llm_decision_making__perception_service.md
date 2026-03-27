# 决策和感知接口文档

最后修改：2026-03-28-03:16

本文档定义 `llm_decision_making` 与 `perception_service` 之间的 HTTP 接口草案。

当前这版文档基于以下已确认前提：

- 文件上传、文件下载、结构化推理解耦
- 大文件不直接内嵌在 JSON 中；请求体和响应体中只传 `artifact_id`
- `llm_decision_making` 负责先从 `robot_service` 获取观测文件，再上传到 `perception_service`
- `perception_service` 默认返回相机坐标系结果；世界坐标系转换仍由 `llm_decision_making.pose_transformer` 负责
- 当前感知链路预计采用“2D 分割 + 单目标 3D 重建”的组合方案，但接口协议不把具体模型实现写死
- 当前接口数量尽量少，但 `PerceptionRequest` 和 `PerceptionResponse` 的 schema 一次性写完整

## 1. 设计目标

`perception_service` 对 `llm_decision_making` 提供以下核心能力：

- 接收决策端上传的观测文件，例如 RGB 图、深度图、点图、已有 mask 等
- 通过单独的下载接口向决策端返回感知侧产出的 mask、3D 模型和调试文件
- 接收结构化推理请求
- 根据任务文本和观测数据执行感知链路
- 返回按实例组织的结构化感知结果，包括：
  - 2D 定位信息
  - 3D 位姿信息
  - 与实例对应的产物引用

## 2. 基本设计原则

### 2.1 文件传输与推理解耦

`perception_service` 中所有体积较大的内容都通过 artifact 接口传输，而不是直接嵌进 `POST /perception/infer` 的 JSON。

也就是说：

- 上传输入文件走 `POST /artifacts`
- 下载输出文件走 `GET /artifacts/{artifact_id}/content`
- `POST /perception/infer` 只处理结构化字段和 artifact 引用

这样做的目的包括：

- 避免 JSON 请求体和响应体过大
- 提高上传和下载速率
- 便于复用同一批输入文件做多次推理
- 便于感知侧返回较多调试产物，而不污染主响应体

### 2.2 面向结构化结果，而不是面向模型内部细节

`llm_decision_making` 关心的是：

- 这次感知请求对应哪些目标物体
- 每个实例的 2D 对应关系是什么
- 每个实例的 3D 位姿是什么
- 相关文件在哪里下载

它不关心感知侧内部到底用了什么框架、什么分割模型、什么 3D 重建模型。

因此协议描述的是：

- 上传什么观测
- 提交什么任务和上下文
- 返回什么结构化结果

而不是：

- 如何调用某个具体 SAM3 API
- 如何调用某个具体 SAM3D-object Python 类

### 2.3 Artifact 是二进制文件的根资源

所有非小型 JSON 字段统一通过 artifact 资源管理。

artifact 的典型用途包括：

- 输入：
  - RGB 图
  - 深度图
  - 点图
  - 外部 mask
- 输出：
  - 实例 mask
  - Gaussian PLY
  - Mesh GLB
  - 点云文件
  - 叠加可视化图
  - 调试 JSON

### 2.4 `POST /perception/infer` 当前采用同步响应

当前版本协议不引入单独的 `perception_job` 资源。

也就是说：

- 决策端发起一次 `POST /perception/infer`
- 感知侧在同一次请求中完成推理
- 同步返回一个 `PerceptionResponse`

如果后续推理耗时明显增长，再考虑扩展成异步 job 模型；当前版本先保持接口数量最少。

### 2.5 默认输出相机坐标系结果

`perception_service` 当前默认输出相机坐标系结果，并在响应体中显式写出：

- `coordinate_frame = "camera"`

这和当前仓库的模块职责一致：

- `perception_service` 负责视觉和 3D 感知计算
- `llm_decision_making.pose_transformer` 负责从相机坐标系转换到世界坐标系

### 2.6 Observation 必须足够支撑 3D 感知

当前协议要求：

- `rgb_artifact_id` 必填
- `depth_artifact_id` 和 `pointmap_artifact_id` 至少提供一个

推荐优先级：

- 如果同时提供 `pointmap_artifact_id` 和 `depth_artifact_id`
  - 感知侧优先使用 `pointmap_artifact_id` 作为 3D 几何来源
- 如果只提供 `depth_artifact_id`
  - 感知侧可结合 `camera_intrinsics` 恢复点图或使用深度做 3D 几何计算

### 2.7 顶层扩展字段统一放入 ext

为了保证协议顶层结构稳定，所有 JSON 请求体和响应体遵循以下规则：

- 第一层只放稳定核心字段
- 后续新增的顶层可选扩展字段统一放入 `ext`
- `ext` 固定存在；如果当前没有扩展字段，则传空对象 `{}`

说明：

- `multipart/form-data` 上传接口本身不是 JSON，因此这一条主要约束 JSON 端点
- 这里约束的是协议顶层字段；已经在 schema 中单独定义的嵌套对象，例如 `observation`、`options`、`scene_artifacts`，内部字段按各自结构约定，不要求再额外包一层 `ext`
- 对上传接口，如果需要补充可选元数据，可通过表单字段 `ext` 传 JSON 字符串；如果没有，则可省略

## 3. 资源模型

### 3.1 Artifact 资源

artifact 表示一个可下载的二进制文件或文件型产物。

建议的 artifact 元数据结构如下：

```json
{
  "artifact_id": "artifact_rgb_20260328024010_0001",
  "artifact_type": "rgb_image",
  "content_type": "image/png",
  "filename": "front_rgb.png",
  "size_bytes": 248531,
  "sha256": "5a731b9f0b5d5d95d0f4e9f1ed3c5b6f9c6c1d6e8e1f0b3c3f1d1b2a9e8d7c6b",
  "created_at": "2026-03-28T02:40:10Z",
  "ext": {}
}
```

建议 `artifact_type` 取值包括：

- `rgb_image`
- `depth_image`
- `pointmap`
- `mask_image`
- `mesh_glb`
- `gaussian_ply`
- `pointcloud_ply`
- `visualization_image`
- `debug_json`

### 3.2 Perception Inference 资源

当前版本不把单次感知推理落成持久化 job 资源。

也就是说：

- 不引入 `/perception/jobs`
- 不引入查询任务状态接口
- 一次推理就是一次同步请求和一次同步响应

### 3.3 结果资源的组织方式

感知结果按“实例”组织。

一个成功识别并完成 3D 重建的实例至少包含：

- 该实例对应的语义标签
- 该实例对应的 2D mask 文件引用
- 该实例的 2D bbox
- 该实例在相机坐标系中的 3D 位姿
- 该实例对应的 3D 产物文件引用

## 4. 接口清单

### 4.1 Artifact 接口

#### 4.1.1 上传 artifact

`POST /artifacts`

作用：

- 上传感知所需的输入文件
- 返回感知侧分配的 `artifact_id`

请求约定：

- `Content-Type: multipart/form-data`
- 表单字段：
  - `file`
    - 必填
    - 二进制文件内容
  - `artifact_type`
    - 必填
    - 取值见上文 artifact 类型枚举
  - `ext`
    - 可选
    - JSON 字符串；如果没有则可省略

请求示例：

说明：

- 这里用 `curl` 只是说明传输形式，正式 client 可以用任意 HTTP 库构造 multipart 请求

```bash
curl -X POST http://perception-service/artifacts \
  -F "artifact_type=rgb_image" \
  -F "file=@front_rgb.png;type=image/png"
```

响应体建议：

```json
{
  "artifact_id": "artifact_rgb_20260328024010_0001",
  "artifact_type": "rgb_image",
  "content_type": "image/png",
  "filename": "front_rgb.png",
  "size_bytes": 248531,
  "sha256": "5a731b9f0b5d5d95d0f4e9f1ed3c5b6f9c6c1d6e8e1f0b3c3f1d1b2a9e8d7c6b",
  "created_at": "2026-03-28T02:40:10Z",
  "ext": {}
}
```

说明：

- 成功时建议返回 HTTP `201 Created`
- `content_type` 以服务端实际识别结果为准
- `artifact_id` 建议采用可读字符串格式：
  - `artifact_<type>_<YYYYMMDDHHMMSS>_<seq>`

#### 4.1.2 下载 artifact 内容

`GET /artifacts/{artifact_id}/content`

作用：

- 下载由感知侧保存的输入或输出文件内容

返回约定：

- 成功时直接返回二进制响应体，而不是 JSON
- `Content-Type` 由具体文件决定，例如：
  - `image/png`
  - `application/x-npz`
  - `model/gltf-binary`
  - `application/octet-stream`
  - `application/json`

说明：

- 当前不单独定义 artifact 元数据查询接口
- 决策端需要的基础元数据由上传响应和推理响应提供

### 4.2 Perception 推理接口

#### 4.2.1 提交推理请求

`POST /perception/infer`

作用：

- 提交结构化感知请求
- 由感知侧执行一次完整推理
- 返回结构化的 2D/3D 感知结果

请求体建议：

```json
{
  "task": {
    "task_id": "1",
    "instruction": "Place the blue_cube on top of the red_cube",
    "object_texts": ["blue_cube", "red_cube"]
  },
  "observation": {
    "camera_id": "front",
    "rgb_artifact_id": "artifact_rgb_20260328024010_0001",
    "depth_artifact_id": "artifact_depth_20260328024011_0002",
    "pointmap_artifact_id": "artifact_pointmap_20260328024011_0003",
    "depth_scale_m_per_unit": 0.001,
    "camera_intrinsics": {
      "fx": 525.0,
      "fy": 525.0,
      "cx": 319.5,
      "cy": 239.5,
      "width": 640,
      "height": 480
    },
    "camera_extrinsics": {
      "translation": [0.0, 0.0, 1.0],
      "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0]
    },
    "camera_frame_id": "camera_front",
    "timestamp": "2026-03-28T02:40:12Z"
  },
  "context": {
    "session_id": "sess_isaac_sim_20260328023950_a1b2",
    "environment_id": "2-ycb",
    "camera_name": "front"
  },
  "options": {
    "include_mask_artifacts": true,
    "include_visualization_artifacts": true,
    "include_debug_artifacts": false,
    "include_mesh_glb_artifacts": true,
    "include_gaussian_ply_artifacts": true,
    "include_pointcloud_artifacts": false,
    "max_objects_per_label": 4
  },
  "ext": {}
}
```

字段说明：

- `task`
  - 必填
  - 表示本次感知对应的任务信息
- `task.task_id`
  - 必填
  - 保留决策端原始任务 id
- `task.instruction`
  - 必填
  - 原始任务文本
- `task.object_texts`
  - 必填
  - 需要感知的目标物体文本列表
  - 当前建议：
    - 非空数组
    - 去重
    - 使用单数或规范化标签

- `observation`
  - 必填
  - 表示一次感知使用的观测数据
- `observation.camera_id`
  - 必填
  - 当前观测对应的相机逻辑 id
- `observation.rgb_artifact_id`
  - 必填
  - RGB 图 artifact 引用
- `observation.depth_artifact_id`
  - 可选
  - 深度图 artifact 引用
- `observation.pointmap_artifact_id`
  - 可选
  - 点图 artifact 引用
- `observation.depth_scale_m_per_unit`
  - 当 `depth_artifact_id` 指向 16-bit PNG 或其他非自描述深度格式时必填
  - 表示深度原始值乘以该比例后得到米单位深度
- `observation.camera_intrinsics`
  - 必填
  - 当前观测对应的相机内参
- `observation.camera_extrinsics`
  - 可选
  - 当前观测对应的相机外参
  - 字段命名跟随 `robot_service` 协议，使用 `quaternion_wxyz`
- `observation.camera_frame_id`
  - 必填
  - 当前相机坐标系名称
- `observation.timestamp`
  - 必填
  - 当前观测时间戳

- `context`
  - 必填
  - 当前请求的外部上下文
- `context.session_id`
  - 可选
  - 如果此次观测来自某个 robot session，则带上
- `context.environment_id`
  - 可选
  - 当前环境 id
- `context.camera_name`
  - 可选
  - 人类可读相机名称

- `options`
  - 必填
  - 控制本次推理希望返回哪些产物
- `options.include_mask_artifacts`
  - 是否返回每个实例 mask 的 artifact 引用
- `options.include_visualization_artifacts`
  - 是否返回叠加可视化图等视觉产物
- `options.include_debug_artifacts`
  - 是否返回调试 JSON 等调试产物
- `options.include_mesh_glb_artifacts`
  - 是否返回 Mesh GLB 产物引用
- `options.include_gaussian_ply_artifacts`
  - 是否返回 Gaussian PLY 产物引用
- `options.include_pointcloud_artifacts`
  - 是否返回点云文件产物引用
- `options.max_objects_per_label`
  - 同一 `object_text` 最多返回多少个实例

关键约束：

- `rgb_artifact_id` 必填
- `depth_artifact_id` 与 `pointmap_artifact_id` 至少提供一个
- 如果二者都提供：
  - 当前协议建议感知侧优先使用 `pointmap_artifact_id`

#### 4.2.2 推理成功响应

响应体建议：

```json
{
  "request_id": "perc_req_20260328024012_0001",
  "success": true,
  "coordinate_frame": "camera",
  "timestamp": "2026-03-28T02:40:15Z",
  "detected_objects": [
    {
      "instance_id": "obj_blue_cube_0001",
      "label": "blue_cube",
      "source_object_text": "blue_cube",
      "score": 0.96,
      "source_mask_artifact_id": "artifact_mask_20260328024014_0101",
      "bbox_2d_xyxy": [122, 188, 214, 286],
      "translation_m": [0.51, 0.12, 0.83],
      "quaternion_wxyz": [0.998, 0.012, 0.050, -0.021],
      "scale_m": [0.045, 0.045, 0.045],
      "mesh_glb_artifact_id": "artifact_mesh_20260328024015_0201",
      "gaussian_ply_artifact_id": "artifact_gaussian_20260328024015_0202",
      "pointcloud_artifact_id": null,
      "ext": {}
    },
    {
      "instance_id": "obj_red_cube_0001",
      "label": "red_cube",
      "source_object_text": "red_cube",
      "score": 0.94,
      "source_mask_artifact_id": "artifact_mask_20260328024014_0102",
      "bbox_2d_xyxy": [305, 191, 392, 281],
      "translation_m": [0.63, -0.04, 0.82],
      "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0],
      "scale_m": [0.045, 0.045, 0.045],
      "mesh_glb_artifact_id": "artifact_mesh_20260328024015_0203",
      "gaussian_ply_artifact_id": "artifact_gaussian_20260328024015_0204",
      "pointcloud_artifact_id": null,
      "ext": {}
    }
  ],
  "scene_artifacts": {
    "visualization_artifact_ids": [
      "artifact_vis_20260328024015_0301"
    ],
    "debug_artifact_ids": []
  },
  "error": {},
  "ext": {
    "matched_object_texts": ["blue_cube", "red_cube"],
    "unmatched_object_texts": []
  }
}
```

字段说明：

- `request_id`
  - 必填
  - 本次感知请求的唯一 id
- `success`
  - 必填
  - 当前请求是否至少成功返回了一个有效 3D 实例
- `coordinate_frame`
  - 必填
  - 当前约定固定为 `camera`
- `timestamp`
  - 必填
  - 感知侧生成本次响应的时间戳
- `detected_objects`
  - 必填
  - 成功识别且成功生成 3D 结果的实例数组
- `scene_artifacts`
  - 必填
  - 本次请求级别的共享产物引用
- `error`
  - 成功时固定返回空对象 `{}`

每个 `detected_objects` 元素说明：

- `instance_id`
  - 感知侧生成的实例唯一 id
- `label`
  - 当前实例的归一化标签
- `source_object_text`
  - 本实例来自哪个 `task.object_texts` 提示词
- `score`
  - 当前实例的整体感知置信度
  - 建议范围 `[0, 1]`
- `source_mask_artifact_id`
  - 当前实例对应的 2D mask 文件引用
- `bbox_2d_xyxy`
  - 当前实例 mask 的外接框，单位是像素，格式为 `xyxy`
- `translation_m`
  - 当前实例在相机坐标系中的平移，单位米
- `quaternion_wxyz`
  - 当前实例在相机坐标系中的四元数，顺序固定为 `wxyz`
- `scale_m`
  - 当前实例三轴尺度，单位米
- `mesh_glb_artifact_id`
  - Mesh GLB 文件 artifact 引用
  - 如果 `options.include_mesh_glb_artifacts = false`，则返回 `null`
- `gaussian_ply_artifact_id`
  - Gaussian PLY 文件 artifact 引用
  - 如果 `options.include_gaussian_ply_artifacts = false`，则返回 `null`
- `pointcloud_artifact_id`
  - 点云文件 artifact 引用
  - 如果 `options.include_pointcloud_artifacts = false`，则返回 `null`

四元数顺序说明：

- 当前这份跨模块协议中的所有四元数字段统一使用 `quaternion_wxyz`
- 这个顺序与 Isaac Sim Core / Camera API 保持一致
- 如果底层 3D 感知库内部使用 `xyzw` 或其他顺序，必须由 `perception_service` 在服务内部完成转换
- `llm_decision_making` 不应承担四元数重排职责

#### 4.2.3 推理业务失败响应

如果请求体合法，artifact 也存在，但推理业务本身失败，例如：

- 所有 `object_texts` 都没有分割出任何有效 mask
- 所有实例都在 3D 重建阶段失败

则建议仍然返回 HTTP `200 OK`，并返回结构化 `PerceptionResponse`：

```json
{
  "request_id": "perc_req_20260328024012_0002",
  "success": false,
  "coordinate_frame": "camera",
  "timestamp": "2026-03-28T02:40:14Z",
  "detected_objects": [],
  "scene_artifacts": {
    "visualization_artifact_ids": [],
    "debug_artifact_ids": [
      "artifact_debug_20260328024014_0401"
    ]
  },
  "error": {
    "code": "SAM3_NO_MASK",
    "message": "No valid mask was produced for the requested object_texts."
  },
  "ext": {
    "matched_object_texts": [],
    "unmatched_object_texts": ["blue_cube", "red_cube"]
  }
}
```

说明：

- `success = false`
- `detected_objects = []`
- `error.code` 和 `error.message` 必填
- 这样 `llm_decision_making` 可以统一按 `PerceptionResponse` 解码，而不需要把业务失败和系统异常混成一类

## 5. Schema 细化约定

### 5.1 Artifact 内容格式建议

为了让 `llm_decision_making` 和 `perception_service` 一次性对齐文件格式，当前建议如下。

#### 5.1.1 RGB 图

- `artifact_type = "rgb_image"`
- 推荐 `content_type = "image/png"`
- 图像格式：
  - `uint8`
  - 三通道
  - 默认 `RGB`

#### 5.1.2 深度图

- `artifact_type = "depth_image"`
- 推荐 `content_type`：
  - `image/png`
  - 或 `application/x-npy`
- 如果是 `image/png`
  - 推荐单通道 16-bit
  - 必须同时提供 `depth_scale_m_per_unit`
- 如果是 `application/x-npy`
  - 推荐 `float32`
  - 单位直接为米

#### 5.1.3 点图

- `artifact_type = "pointmap"`
- 推荐 `content_type = "application/x-npz"`
- 推荐文件内容：
  - `points`
    - shape: `[H, W, 3]`
    - dtype: `float32`
    - 单位：米
    - 坐标系：相机坐标系

说明：

- 当前协议不强制点图必须采用某个具体内部 key 名，但推荐统一使用 `points`
- 如果后续确实需要额外数组，可放在文件内部；协议层不直接关心内部实现细节

### 5.2 `camera_intrinsics`

建议结构：

```json
{
  "fx": 525.0,
  "fy": 525.0,
  "cx": 319.5,
  "cy": 239.5,
  "width": 640,
  "height": 480
}
```

字段说明：

- `fx`, `fy`
  - 焦距
- `cx`, `cy`
  - 主点
- `width`, `height`
  - 对应图像分辨率

### 5.3 `camera_extrinsics`

建议结构：

```json
{
  "translation": [0.0, 0.0, 1.0],
  "quaternion_wxyz": [1.0, 0.0, 0.0, 0.0]
}
```

字段说明：

- `translation`
  - 相机外参平移
- `quaternion_wxyz`
  - 顺序固定为 `wxyz`
  - 当前也作为本协议所有四元数字段的统一顺序，并与 Isaac Sim Core / Camera API 保持一致

### 5.4 `scene_artifacts`

建议结构：

```json
{
  "visualization_artifact_ids": [
    "artifact_vis_20260328024015_0301"
  ],
  "debug_artifact_ids": [
    "artifact_debug_20260328024015_0401"
  ]
}
```

说明：

- `visualization_artifact_ids`
  - 例如：
    - mask overlay 图
    - 实例编号叠加图
- `debug_artifact_ids`
  - 例如：
    - 调试 JSON
    - 中间结果摘要

## 6. 错误响应建议

### 6.1 Artifact 接口错误响应

artifact 上传、下载等非推理接口在失败时建议统一使用如下错误结构：

```json
{
  "error_code": "NOT_FOUND",
  "message": "Requested artifact not found.",
  "ext": {
    "details": {
      "artifact_id": "artifact_rgb_20260328024010_0001"
    }
  }
}
```

### 6.2 `POST /perception/infer` 的错误分类

`POST /perception/infer` 建议区分两类失败：

1. 请求级错误
   - 例如 JSON 缺字段、artifact 不存在、artifact 类型不匹配
   - 建议返回 HTTP `4xx`
   - 使用通用错误结构

2. 业务级失败
   - 例如模型没有找到任何有效目标、3D 重建失败
   - 建议返回 HTTP `200`
   - 使用 `PerceptionResponse`，但 `success = false`

### 6.3 常见错误码

当前建议支持以下错误码：

- `INVALID_REQUEST`
  - 请求体缺字段、字段格式错误
- `ARTIFACT_NOT_FOUND`
  - 请求引用的 artifact 不存在
- `ARTIFACT_TYPE_MISMATCH`
  - artifact 类型与当前字段要求不匹配
- `UNSUPPORTED_CONTENT_TYPE`
  - 文件内容类型不支持
- `MISSING_GEOMETRY_SOURCE`
  - `depth_artifact_id` 与 `pointmap_artifact_id` 都缺失
- `SAM3_NO_MASK`
  - 所有 `object_texts` 均未得到有效 mask
- `SAM3D_INFERENCE_FAILED`
  - 3D 重建阶段失败
- `INTERNAL_ERROR`
  - 未归类服务端内部异常

## 7. 典型调用顺序

当前推荐的调用顺序如下：

1. `llm_decision_making` 从 `robot_service` 获取当前相机观测
2. 决策端下载 RGB 图、深度图或点图文件
3. 决策端把这些文件上传到 `perception_service`
   - `POST /artifacts`
4. 决策端拿到各自的 `artifact_id`
5. 决策端发起一次 `POST /perception/infer`
6. 感知侧返回结构化 `PerceptionResponse`
7. 如果需要 mask、GLB、PLY、调试图，决策端再按需调用：
   - `GET /artifacts/{artifact_id}/content`
8. 决策端把响应中的相机坐标系结果交给 `pose_transformer`
9. 后续再把转换后的感知结果交给 `policy_model` 和 `policy_executor`

## 8. 与当前 `llm_decision_making` 的直接对接约束

为了让这份协议和当前仓库已有约定保持一致，建议决策端按以下方式接入：

- `task.task_id`
  - 直接复用 `SourceTask.task_id` / `ParsedTask.task_id`
- `task.instruction`
  - 直接复用原始任务文本
- `task.object_texts`
  - 直接复用 `ParsedTask.object_texts`
- `observation.camera_intrinsics`
  - 直接来自 `robot_service` 的 `GET /sessions/{session_id}/cameras`
- `observation.camera_extrinsics`
  - 直接来自 `robot_service` 的 `GET /sessions/{session_id}/cameras`
- `context.session_id`
  - 直接复用机器人侧 `session_id`
- `context.environment_id`
  - 直接复用当前运行时 `objects_env_id`

## 9. 可选健康检查接口

如果后续需要补一个极简健康检查，建议使用：

`GET /healthz`

响应体建议：

```json
{
  "service": "perception_service",
  "status": "ok",
  "ext": {}
}
```

这个接口不是当前核心调用链必需接口，只作为可选补充。
