# Git Worktree 安排

后续仓库按 5 个分支配合 `git worktree` 开发：

- `main`：主分支，只用于集成与发布
- `feature/web`：前端界面，负责用户输入与结果展示
- `feature/llm-decision-making`：任务解析、策略生成与调度
- `feature/robot-service`：机器人执行、摄像头采集与任务接收
- `feature/perception-service`：视觉与 3D 感知计算

建议 `main` 保持单独工作目录，其余 4 个功能分支各自对应一个 worktree，开发时只修改本模块相关内容。跨模块接口协议文档统一维护在 `docs/protocols/`，合并前先同步最新 `main`，再分别并回主分支。
