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
- `docs/SAM3D-object_使用指南.md`
  - 说明 `SAM3D-object` 仓库怎么安装、推理、看输出，以及怎样接到本仓库的 `perception_service`
- `docs/ultralytics_SAM3_使用指南.md`
  - 说明 `ultralytics` 包里 SAM3 的几种官方接口、适用场景和推荐调用方式

## 说明

- `SAM3D-object/` 目前保留为独立克隆仓库，便于直接阅读上游代码和提交历史。
- 如果本地还没有这个目录，需要自行执行：
  - `git clone https://github.com/facebookresearch/sam-3d-objects.git perception_service/SAM3D-object`
- 这两个指南文档都基于当前本地代码快照和上游官方文档整理，没有在本机做完整推理验证。
- 主要限制是：
  - `SAM3D-object` 官方要求 Linux + NVIDIA GPU + 至少 32GB 显存
  - `SAM3D-object` 和 `ultralytics` SAM3 都依赖 Hugging Face 权重访问权限
