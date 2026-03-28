# 决策和感知接口文档

最后修改：2026-03-29

本文档定义 `llm_decision_making` 与 `perception_service` 之间的 HTTP 协议。

## 1. 服务边界

- `llm_decision_making`
  - 提供任务文本
  - 提供一个或多个相机观测
  - 上传 RGB / depth 文件
  - 调用感知推理接口
- `perception_service`
  - 保存上传的 artifact
  - 基于每个观测内部生成 `pointmap`
  - 调用内部 SAM3 / SAM3D-object 推理
  - 返回结构化结果和可下载 artifact 引用

固定约定：

- 请求中不上传 `pointmap`
- 请求中不上传 `mask_image`
- `mask_image` 是感知侧推理产物
- 当前协议不包含 `jobs`
- `POST /perception/infer` 是同步接口

## 2. 通用约定

### 2.1 顶层 `ext`

所有 JSON 请求体和响应体都包含顶层 `ext`。

- 类型：`object`
- 必填：是
- 无扩展信息时传 `{}` 

### 2.2 坐标系

- 感知结果默认输出相机坐标系
- `coordinate_frame` 当前固定为 `"camera"`

### 2.3 Artifact 类型

支持的 `artifact_type`：

- `rgb_image`
- `depth_image`
- `mask_image`
- `mesh_glb`
- `gaussian_ply`
- `pointcloud_ply`
- `visualization_image`
- `debug_json`

## 3. 接口清单

### 3.1 `GET /healthz`

作用：

- 健康检查

响应体：

```json
{
  "service": "perception_service",
  "status": "ok",
  "ext": {}
}
```

字段：

- `service`
  - 类型：`string`
  - 必填：是
- `status`
  - 类型：`string`
  - 必填：是
- `ext`
  - 类型：`object`
  - 必填：是

### 3.2 `POST /artifacts`

作用：

- 上传输入文件

请求：

- `Content-Type: multipart/form-data`

表单字段：

- `file`
  - 类型：二进制文件
  - 必填：是
- `artifact_type`
  - 类型：`string`
  - 必填：是
  - 允许值见 `2.3`
- `ext`
  - 类型：JSON 字符串
  - 必填：否

响应体：

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

字段：

- `artifact_id`
  - 类型：`string`
  - 必填：是
- `artifact_type`
  - 类型：`string`
  - 必填：是
- `content_type`
  - 类型：`string`
  - 必填：是
- `filename`
  - 类型：`string`
  - 必填：是
- `size_bytes`
  - 类型：`integer`
  - 必填：是
- `sha256`
  - 类型：`string`
  - 必填：是
- `created_at`
  - 类型：`string`，RFC 3339 时间
  - 必填：是
- `ext`
  - 类型：`object`
  - 必填：是

状态码：

- 成功：`201 Created`

### 3.3 `GET /artifacts/{artifact_id}/content`

作用：

- 下载 artifact 内容

路径参数：

- `artifact_id`
  - 类型：`string`
  - 必填：是

响应：

- 成功时直接返回文件二进制内容
- `Content-Type` 由具体 artifact 决定

### 3.4 `POST /perception/infer`

作用：

- 提交感知推理请求
- 服务端按 `observations[]` 逐个处理

请求体：

```json
{
  "task": {
    "task_id": "1",
    "instruction": "Place the blue_cube on top of the red_cube",
    "object_texts": ["blue_cube", "red_cube"]
  },
  "observations": [
    {
      "camera_id": "table_top",
      "rgb_image": {
        "content_type": "image/png",
        "artifact_id": "artifact_rgb_20260328024010_0001"
      },
      "depth_image": {
        "content_type": "application/x-npy",
        "artifact_id": "artifact_depth_20260328024011_0002"
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
        "quaternion_wxyz": [0.7071, 0.0, 0.7071, 0.0]
      },
      "timestamp": "2026-03-28T02:40:12Z",
      "ext": {
        "depth_unit": "meter",
        "depth_encoding": "npy-float32",
        "view_mode": "top_down",
        "camera_frame_id": "camera_front"
      }
    }
  ],
  "context": {
    "session_id": "sess_isaac_sim_20260328023950_a1b2",
    "environment_id": "2-ycb"
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

#### 3.4.1 `task`

- `task_id`
  - 类型：`string`
  - 必填：是
- `instruction`
  - 类型：`string`
  - 必填：是
- `object_texts`
  - 类型：`string[]`
  - 必填：是
  - 约束：至少 1 个元素

#### 3.4.2 `observations`

- 类型：`array`
- 必填：是
- 约束：至少 1 个元素

每个元素字段：

- `camera_id`
  - 类型：`string`
  - 必填：是
- `rgb_image`
  - 类型：`object`
  - 必填：是
- `depth_image`
  - 类型：`object`
  - 必填：是
- `intrinsics`
  - 类型：`object`
  - 必填：是
- `extrinsics`
  - 类型：`object | null`
  - 必填：否
- `timestamp`
  - 类型：`string`，RFC 3339 时间
  - 必填：是
- `ext`
  - 类型：`object`
  - 必填：是

`rgb_image` 字段：

- `artifact_id`
  - 类型：`string`
  - 必填：是
- `content_type`
  - 类型：`string`
  - 必填：否

`depth_image` 字段：

- `artifact_id`
  - 类型：`string`
  - 必填：是
- `content_type`
  - 类型：`string`
  - 必填：否

`intrinsics` 字段：

- `fx`
  - 类型：`number`
  - 必填：是
- `fy`
  - 类型：`number`
  - 必填：是
- `cx`
  - 类型：`number`
  - 必填：是
- `cy`
  - 类型：`number`
  - 必填：是
- `width`
  - 类型：`integer`
  - 必填：是
  - 约束：`> 0`
- `height`
  - 类型：`integer`
  - 必填：是
  - 约束：`> 0`

`extrinsics` 字段：

- `translation`
  - 类型：`number[3]`
  - 必填：是
- `quaternion_wxyz`
  - 类型：`number[4]`
  - 必填：是

`observations[i].ext` 支持字段：

- `depth_scale_m_per_unit`
  - 类型：`number`
  - 必填：否
  - 约束：`> 0`
  - 说明：当深度图为整数格式时必填
- `depth_unit`
  - 类型：`string`
  - 必填：否
- `depth_encoding`
  - 类型：`string`
  - 必填：否
- `view_mode`
  - 类型：`string`
  - 必填：否
- `camera_frame_id`
  - 类型：`string`
  - 必填：否

#### 3.4.3 `context`

- `session_id`
  - 类型：`string | null`
  - 必填：否
- `environment_id`
  - 类型：`string | null`
  - 必填：否

#### 3.4.4 `options`

- `include_mask_artifacts`
  - 类型：`boolean`
  - 必填：是
- `include_visualization_artifacts`
  - 类型：`boolean`
  - 必填：是
- `include_debug_artifacts`
  - 类型：`boolean`
  - 必填：是
- `include_mesh_glb_artifacts`
  - 类型：`boolean`
  - 必填：是
- `include_gaussian_ply_artifacts`
  - 类型：`boolean`
  - 必填：是
- `include_pointcloud_artifacts`
  - 类型：`boolean`
  - 必填：是
- `max_objects_per_label`
  - 类型：`integer`
  - 必填：是
  - 约束：`> 0`

#### 3.4.5 请求级约束

- 请求中不允许出现 `pointmap_artifact_id`
- 如果任一 `observations[i]` 非法，则整个请求返回 `4xx`
- `pointmap` 由服务端根据 `depth_image + intrinsics` 内部生成

#### 3.4.6 响应体

```json
{
  "request_id": "perc_req_20260328024012_0001",
  "success": true,
  "timestamp": "2026-03-28T02:40:15Z",
  "observation_results": [
    {
      "camera_id": "table_top",
      "observation_timestamp": "2026-03-28T02:40:12Z",
      "success": true,
      "coordinate_frame": "camera",
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
        }
      ],
      "scene_artifacts": {
        "visualization_artifact_ids": [
          "artifact_vis_20260328024015_0301"
        ],
        "debug_artifact_ids": []
      },
      "error": {},
      "ext": {}
    }
  ],
  "error": {},
  "ext": {}
}
```

顶层字段：

- `request_id`
  - 类型：`string`
  - 必填：是
- `success`
  - 类型：`boolean`
  - 必填：是
  - 说明：至少一个观测成功返回有效 3D 实例时为 `true`
- `timestamp`
  - 类型：`string`，RFC 3339 时间
  - 必填：是
- `observation_results`
  - 类型：`array`
  - 必填：是
- `error`
  - 类型：`object`
  - 必填：是
- `ext`
  - 类型：`object`
  - 必填：是

每个 `observation_results[i]` 字段：

- `camera_id`
  - 类型：`string`
  - 必填：是
- `observation_timestamp`
  - 类型：`string`，RFC 3339 时间
  - 必填：是
- `success`
  - 类型：`boolean`
  - 必填：是
- `coordinate_frame`
  - 类型：`string`
  - 必填：是
  - 当前固定值：`"camera"`
- `detected_objects`
  - 类型：`array`
  - 必填：是
- `scene_artifacts`
  - 类型：`object`
  - 必填：是
- `error`
  - 类型：`object`
  - 必填：是
- `ext`
  - 类型：`object`
  - 必填：是

每个 `detected_objects[i]` 字段：

- `instance_id`
  - 类型：`string`
  - 必填：是
- `label`
  - 类型：`string`
  - 必填：是
- `source_object_text`
  - 类型：`string`
  - 必填：是
- `score`
  - 类型：`number`
  - 必填：是
- `source_mask_artifact_id`
  - 类型：`string | null`
  - 必填：是
- `bbox_2d_xyxy`
  - 类型：`integer[4]`
  - 必填：是
- `translation_m`
  - 类型：`number[3]`
  - 必填：是
- `quaternion_wxyz`
  - 类型：`number[4]`
  - 必填：是
- `scale_m`
  - 类型：`number[3]`
  - 必填：是
- `mesh_glb_artifact_id`
  - 类型：`string | null`
  - 必填：是
- `gaussian_ply_artifact_id`
  - 类型：`string | null`
  - 必填：是
- `pointcloud_artifact_id`
  - 类型：`string | null`
  - 必填：是
- `ext`
  - 类型：`object`
  - 必填：是

`scene_artifacts` 字段：

- `visualization_artifact_ids`
  - 类型：`string[]`
  - 必填：是
- `debug_artifact_ids`
  - 类型：`string[]`
  - 必填：是

#### 3.4.7 状态码

- 请求字段或 artifact 非法：`4xx`
- 请求字段合法但推理业务失败：`200`
- 推理业务失败时：
  - 顶层响应仍符合 `PerceptionResponse`
  - `success = false`
  - 对应观测的 `observation_results[i].success = false`

### 3.5 错误响应

非推理业务失败时，统一返回：

```json
{
  "error_code": "INVALID_REQUEST",
  "message": "Request validation failed.",
  "ext": {
    "details": {}
  }
}
```

字段：

- `error_code`
  - 类型：`string`
  - 必填：是
- `message`
  - 类型：`string`
  - 必填：是
- `ext`
  - 类型：`object`
  - 必填：是

建议错误码：

- `INVALID_REQUEST`
- `ARTIFACT_NOT_FOUND`
- `ARTIFACT_TYPE_MISMATCH`
- `UNSUPPORTED_CONTENT_TYPE`
- `MISSING_GEOMETRY_SOURCE`
- `SAM3_NO_MASK`
- `SAM3D_INFERENCE_FAILED`
- `INTERNAL_ERROR`
