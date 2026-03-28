# perception_service

当前分支的感知服务工作区。

## 当前内容

- `SAM3D-object/`
  - 从 GitHub 克隆的 `facebookresearch/sam-3d-objects` 代码快照
  - 本地保留、Git 忽略，不纳入当前仓库版本管理
  - 当前本地快照提交：`81a8237`
- `sam3-ultralytics/`
  - 放当前仓库里基于 `ultralytics` 使用 SAM3 模型的脚本、适配层和配置
  - 本地模型权重与权限相关文件单独保留，不直接提交到主仓库
- `pyproject.toml`
  - `uv` 管理的 API 层项目
  - 只负责 HTTP API、artifact 管理和推理调度
- `app.py`
  - `uvicorn` 启动入口
- `perception_service_api/`
  - 当前感知服务的 FastAPI 应用、schema 和服务层实现
- `backend_scripts/`
  - 放感知层调用外部 conda 模型环境时使用的桥接脚本
- `docs/SAM3D-object_使用指南.md`
  - 说明 `SAM3D-object` 仓库怎么安装、推理、看输出，以及怎样接到本仓库的 `perception_service`
- `docs/进程与环境说明.md`
  - 明确 API 层、SAM3、SAM3D-object 各自使用的运行环境、路径和职责边界
- `docs/ultralytics_SAM3_使用指南.md`
  - 说明 `ultralytics` 包里 SAM3 的几种官方接口、适用场景和推荐调用方式

## 说明

- `SAM3D-object/` 目前保留为独立克隆仓库，便于直接阅读上游代码和提交历史。
- 如果本地还没有这个目录，需要自行执行：
  - `git clone https://github.com/facebookresearch/sam-3d-objects.git perception_service/SAM3D-object`
- 当前 `uv` 项目只用于启动和开发 `perception_service` 的 API 层。
- 模型推理环境继续分离：
  - `sam3` 使用独立 conda 环境 `sam3`
  - `SAM3D-object` 使用独立 conda 环境 `sam3d-objects`
- 进程与环境分工以 `docs/进程与环境说明.md` 为准。
- 当前最小 API 骨架已经包含：
  - `GET /healthz`
  - `POST /artifacts`
  - `GET /artifacts/{artifact_id}/content`
  - `POST /perception/infer`
- 当前 `POST /perception/infer` 已完成：
  - 协议字段校验
  - RGB / depth artifact 读取
  - `depth + camera_intrinsics -> pointmap` 内部生成
  - `sam3` / `sam3d-objects` 子进程桥接
  - 可选 debug artifact 输出
- 当前 `POST /perception/infer` 还没有完成：
  - `sam3` 真实 2D 分割后端接入
  - `SAM3D-object` 真实 3D 重建后端接入
- 本地启动 API：
  - `cd perception_service && .venv/bin/uvicorn app:app --reload`
- 这两个指南文档都基于当前本地代码快照和上游官方文档整理，没有在本机做完整推理验证。
- 主要限制是：
  - `SAM3D-object` 官方要求 Linux + NVIDIA GPU + 至少 32GB 显存
  - `SAM3D-object` 和 `ultralytics` SAM3 都依赖 Hugging Face 权重访问权限
