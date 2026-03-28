# perception_service

`perception_service/` 是机械臂抓取系统里的感知与 3D 计算模块。

`llm_decision_making` 是它的上游调用方，通过 HTTP 上传 RGB、深度图和任务上下文。
`SAM3` 和 `SAM3D-object` 是它在本机调度的模型后端，通过子进程执行，不直接暴露给上游。

它的职责不是解析任务，也不是执行机器人动作，而是：
- 接收 `llm_decision_making` 上传的 artifact 和感知请求
- 校验请求字段、artifact 类型和图像尺寸
- 基于 `depth + intrinsics` 在服务内部生成 `pointmap`
- 调度本机的 `SAM3` 2D 分割后端和 `SAM3D-object` 3D 重建后端
- 把 mask、位姿、mesh、pointcloud 等结果整理成协议要求的结构化响应
- 管理本模块运行时产生的 artifact 和 debug 数据

从本模块的视角看：
- `llm_decision_making` 是上游 HTTP 客户端
- `SAM3` 是本机 2D 分割黑盒
- `SAM3D-object` 是本机 3D 重建黑盒

也就是说，`perception_service` 的 API 层不关心上游怎么做任务解析，也不把模型重依赖直接揉进 FastAPI 进程里。  
它只关心三件事：1. 收到什么请求 2. 该如何调度本机模型 3. 最终要返回什么结构化感知结果。

## 运行时落盘

当前运行时产物以 artifact 为基本单元，统一落在 `runtime/artifacts/` 下：

```text
runtime/
  artifacts/
    artifact_rgb_image_20260328024010_xxxx/
      content
      metadata.json
    artifact_depth_image_20260328024011_xxxx/
      content
      metadata.json
    artifact_debug_json_20260328132318_xxxx/
      content
      metadata.json
```

当前约定如下：
- 每个 artifact 使用单独目录保存
- 二进制内容统一写到 `content`
- 结构化元数据统一写到 `metadata.json`
- 如果 `include_debug_artifacts=true`，会额外保存 `debug_json` artifact
- 当前模块还没有实现类似 `llm_decision_making/runs/` 的 run 级日志目录；现阶段以 artifact 落盘和 API 错误响应为主

## 组成

### 1. API 主进程

主入口是 `app.py` 和 `api/app.py`。

这层负责：
- 创建 FastAPI 应用
- 注册 `health`、`artifacts`、`inference` 三组路由
- 初始化 `ArtifactStore` 和 `PerceptionInferenceService`
- 统一处理 `ApiError` 和请求校验错误

它不负责直接加载 `SAM3` 或 `SAM3D-object` 的重依赖。

### 2. `artifacts` 路由与 artifact 管理

`api/routers/artifacts.py` 和 `api/services/artifact_store.py` 负责：
- 接收 `POST /artifacts`
- 保存上传文件内容
- 生成 `artifact_id`
- 计算 `sha256`
- 返回可下载的 artifact 元数据
- 通过 `GET /artifacts/{artifact_id}/content` 对外提供下载

当前 artifact 类型包括：
- `rgb_image`
- `depth_image`
- `mask_image`
- `mesh_glb`
- `gaussian_ply`
- `pointcloud_ply`
- `visualization_image`
- `debug_json`

### 3. `inference_service`

`api/services/inference_service.py` 是当前的感知主编排层。

它当前已经完成：
- 为每次请求生成 `request_id`
- 探测 `SAM3` / `SAM3D-object` 后端脚本和解释器是否可用
- 逐个处理 `observations[]`
- 读取 RGB / depth artifact
- 校验 RGB 分辨率和 `intrinsics.width/height` 一致
- 把深度图转换成内部 `pointmap`
- 按需写出 preflight `debug_json`
- 返回符合协议的 `PerceptionResponse`

它当前还没有完成：
- `SAM3` 真实 2D 分割结果接入
- `SAM3D-object` 真实 3D 重建结果接入
- `mask_image` / `mesh_glb` / `gaussian_ply` / `pointcloud_ply` 的正式落盘与回传

### 4. `pointmap` 生成

`api/services/pointmap.py` 负责：
- 读取 PNG / NPY 深度图
- 根据 `depth_scale_m_per_unit` 处理整数深度图
- 校验深度图是单通道 2D 数组
- 基于 `fx/fy/cx/cy/width/height` 生成相机坐标系下的 `pointmap`

这里固定了当前模块边界：
- `pointmap` 是感知层内部中间结果
- 不由 `llm_decision_making` 上传
- 不对外作为共享协议字段暴露

### 5. 后端桥接

`api/services/backend_runner.py` 提供统一的子进程调用包装：
- 用指定 Python 解释器启动指定脚本
- 通过标准输入传 JSON
- 从标准输出读取 JSON
- 在失败时返回结构化 `status`、`stdout`、`stderr`

当前桥接脚本包括：
- `sam3-ultralytics/run_sam3_inference.py`
- `backend_scripts/run_sam3d_inference.py`

现在这两个脚本都还处于 stub 状态，`preflight` 能跑通，但还不会产出真实检测结果。

### 6. `SAM3` 接入层

`sam3-ultralytics/` 是当前仓库里 `SAM3` 的本地接入层目录。

它的定位是：
- 保存基于 `ultralytics` 的脚本、适配层和配置
- 作为 API 层调用 `SAM3` 的唯一仓库内入口
- 不把权重文件直接提交到仓库

当前机器上的固定约定：
- conda 环境名：`sam3`
- 环境路径：`/root/autodl-tmp/conda/envs/sam3`
- 权重真实路径：`/root/sam3.pt`
- 仓库内入口路径：`perception_service/sam3-ultralytics/sam3.pt`
- 入口路径应保持为软链接：`sam3.pt -> /root/sam3.pt`

### 7. `SAM3D-object` 接入层

`SAM3D-object/` 是本地保留的上游仓库 checkout，用于 3D 单目标重建。

它的定位是：
- 保存上游研究仓库代码快照
- 作为 3D 重建实现的本地依赖
- 通过 `backend_scripts/run_sam3d_inference.py` 被 API 层调度

当前机器上的固定约定：
- conda 环境名：`sam3d-objects`
- 环境路径：`/root/autodl-tmp/conda/envs/sam3d-objects`
- 权重真实目录：`/root/hf`
- 仓库内入口路径：`perception_service/SAM3D-object/checkpoints/hf`
- 入口路径应保持为软链接：`checkpoints/hf -> /root/hf`

## 运行环境与权重

### 1. API 层环境

API 层使用 `uv` 管理的轻量虚拟环境：
- 项目文件：`perception_service/pyproject.toml`
- 锁文件：`perception_service/uv.lock`
- 虚拟环境：`perception_service/.venv`

当前 API 层依赖只包括：
- `fastapi`
- `uvicorn`
- `python-multipart`
- `numpy`
- `pillow`

本地启动方式：

```bash
cd perception_service
.venv/bin/uvicorn app:app --reload
```

### 2. 模型环境分离

当前固定把模型依赖和 API 层拆开：
- API 进程跑在 `.venv`
- `SAM3` 跑在 conda 环境 `sam3`
- `SAM3D-object` 跑在 conda 环境 `sam3d-objects`

不要把 `ultralytics`、`torch`、`pytorch3d`、`flash_attn`、`kaolin` 这类重依赖直接装进 API 层 `.venv`。

### 3. 权重软链接恢复

如果权重入口软链接丢失，当前机器按下面命令恢复：

```bash
ln -s /root/sam3.pt /root/robot_task/perception_service/sam3-ultralytics/sam3.pt
ln -s /root/hf /root/robot_task/perception_service/SAM3D-object/checkpoints/hf
```

如果目标路径已经存在，先确认是不是错误文件或错误目录，不要直接覆盖。

## 数据结构实例

### `ArtifactMetadata`

```json
{
  "artifact_id": "artifact_rgb_image_20260328024010_0001",
  "artifact_type": "rgb_image",
  "content_type": "image/png",
  "filename": "front_rgb.png",
  "size_bytes": 248531,
  "sha256": "5a731b9f0b5d5d95d0f4e9f1ed3c5b6f9c6c1d6e8e1f0b3c3f1d1b2a9e8d7c6b",
  "created_at": "2026-03-28T02:40:10Z",
  "ext": {}
}
```

### `ObservationPayload`

```json
{
  "camera_id": "table_top",
  "rgb_image": {
    "artifact_id": "artifact_rgb_image_20260328024010_0001"
  },
  "depth_image": {
    "artifact_id": "artifact_depth_image_20260328024011_0002"
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
    "depth_scale_m_per_unit": 0.001,
    "depth_unit": "millimeter",
    "depth_encoding": "png-uint16",
    "camera_frame_id": "camera_front"
  }
}
```

说明：
- `rgb_image` 和 `depth_image` 只传 artifact 引用
- `depth_scale_m_per_unit` 当前放在 `observations[].ext`
- `extrinsics` 可以为空
- 当前 schema 兼容部分旧字段名，但新代码应统一使用协议里的正式字段

### `PerceptionResponse`

```json
{
  "request_id": "perc_req_20260328132318_6fb2d4aa",
  "success": false,
  "timestamp": "2026-03-28T13:23:18Z",
  "observation_results": [
    {
      "camera_id": "table_top",
      "observation_timestamp": "2026-03-28T02:40:12Z",
      "success": false,
      "coordinate_frame": "camera",
      "detected_objects": [],
      "scene_artifacts": {
        "visualization_artifact_ids": [],
        "debug_artifact_ids": [
          "artifact_debug_json_20260328132318_8bdbfbda"
        ]
      },
      "error": {
        "code": "INTERNAL_ERROR",
        "message": "Inference backends are not producing detections yet for this observation. Request validation and internal pointmap generation completed."
      },
      "ext": {
        "pointmap_generated": true
      }
    }
  ],
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Inference backends are not producing detections yet. Request validation and internal pointmap generation completed for all observations."
  },
  "ext": {
    "matched_object_texts": [],
    "unmatched_object_texts": ["blue_cube", "red_cube"],
    "processed_camera_ids": ["table_top"],
    "pointmap_generated_camera_ids": ["table_top"]
  }
}
```

说明：
- 这是当前 stub 阶段的典型返回
- `coordinate_frame` 当前固定为 `"camera"`
- 后续真实后端接通后，`detected_objects` 和 artifact 引用会变成主内容

## 典型数据流

`perception_service` 当前推荐链路如下：

1. `llm_decision_making` 先调用 `POST /artifacts` 上传 RGB 图和深度图
2. `llm_decision_making` 再调用 `POST /perception/infer`，提交 `task`、`observations[]`、`context`、`options`
3. API 层读取 artifact 元数据和内容
4. `inference_service` 校验 artifact 类型和图像尺寸
5. `pointmap.py` 在服务内部把 `depth + intrinsics` 转成 `pointmap`
6. `backend_runner.py` 探测并调用 `SAM3` / `SAM3D-object` 桥接脚本
7. 如果开启 `include_debug_artifacts`，保存 preflight `debug_json`
8. API 层组装 `PerceptionResponse` 返回给上游

后续真实推理链路接通后，会在第 6 到第 8 步之间继续增加：
- 由 `SAM3` 生成 mask / bbox / score
- 由 `SAM3D-object` 基于单物体 mask 和 pointmap 生成 3D 结果
- 把 `mask_image`、`mesh_glb`、`gaussian_ply`、`pointcloud_ply` 等 artifact 保存并回传引用

## 当前目录中的关键文件

- `app.py`
  - `uvicorn` 启动入口
- `api/app.py`
  - FastAPI 应用工厂
- `api/routers/health.py`
  - `GET /healthz`
- `api/routers/artifacts.py`
  - `POST /artifacts` 和 `GET /artifacts/{artifact_id}/content`
- `api/routers/inference.py`
  - `POST /perception/infer`
- `api/schemas.py`
  - API 使用的 Pydantic schema 和协议结构
- `api/settings.py`
  - API 层运行目录、模型解释器路径和桥接脚本路径
- `api/services/artifact_store.py`
  - artifact 落盘与元数据读取
- `api/services/pointmap.py`
  - 深度图解析和 pointmap 生成
- `api/services/backend_runner.py`
  - 子进程 JSON 调度包装
- `api/services/inference_service.py`
  - 感知主编排逻辑
- `sam3-ultralytics/run_sam3_inference.py`
  - `SAM3` 桥接脚本
- `backend_scripts/run_sam3d_inference.py`
  - `SAM3D-object` 桥接脚本
- `docs/进程与环境说明.md`
  - API / SAM3 / SAM3D-object 进程边界、环境路径和权重入口
- `docs/ultralytics_SAM3_使用指南.md`
  - `SAM3` 调用方式整理
- `docs/SAM3D-object_使用指南.md`
  - `SAM3D-object` 接入说明

## 仓库根目录中的共享协议文档

- `docs/protocols/llm_decision_making__perception_service.md`
  - `llm_decision_making` 与 `perception_service` 的共享 HTTP 协议文档

## 一句话总结

`perception_service` 是一个只关心“artifact、pointmap、模型调度、结构化感知输出”的模块；  
对上游 `llm_decision_making` 来说，它是 HTTP 黑盒；对 API 层来说，`SAM3` 和 `SAM3D-object` 也是本机黑盒。
