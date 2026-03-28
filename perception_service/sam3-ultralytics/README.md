# sam3-ultralytics

这个目录用于放当前仓库里基于 `ultralytics` 使用 `SAM3` 模型的代码。

当前仓库约定：

- `perception_service` 里提到的 `SAM3` 后端，默认就是指这里这套 `sam3-ultralytics/` 接入层
- 这里存放的是仓库内脚本、适配层和配置，不是 API 层 `.venv`
- 真实推理依赖固定在 conda 环境 `sam3`
- `SAM3D-object` 的真实推理依赖固定在单独的 conda 环境 `sam3d-objects`
- `sam3.pt` 的真实文件固定放在家目录 `/root/sam3.pt`
- 当前目录下应保留软链接：
  - `sam3.pt -> /root/sam3.pt`

如果软链接丢失，可在仓库根目录执行：

```bash
ln -s /root/sam3.pt /root/robot_task/perception_service/sam3-ultralytics/sam3.pt
```

当前约定：

- 可提交内容：适配脚本、推理封装、配置文件、示例代码
- 本地保留内容：模型权重、鉴权文件、临时输出

相关文档：

- `../docs/ultralytics_SAM3_使用指南.md`
- `../docs/SAM3D-object_使用指南.md`
