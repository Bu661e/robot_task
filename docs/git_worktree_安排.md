# Git Worktree 安排

本文档约定本仓库使用“`main` 作为唯一集成主线，4 个模块分支长期存在”的开发方式。

## 1. 分支职责

仓库按 5 个分支配合 `git worktree` 开发：

- `main`
  - 主分支
  - 只用于集成、验证和发布
- `feature/web`
  - 前端界面
  - 负责用户输入与结果展示
- `feature/llm-decision-making`
  - 决策模块
  - 负责任务解析、策略生成与调度
- `feature/robot-service`
  - 机器人服务
  - 负责机器人执行、摄像头采集与任务接收
- `feature/perception-service`
  - 感知服务
  - 负责视觉与 3D 感知计算

建议 `main` 保持单独工作目录，其余 4 个功能分支各自对应一个 worktree。

## 2. 总体原则

- `main` 是唯一的集成基线，不在 `main` 上直接开发模块业务代码。
- 4 个 `feature/*` 分支可以长期保留，但它们不是发布基线，只是各模块的开发通道。
- 每个模块分支只修改本模块目录和必要的共享文档。
- 跨模块共享协议文档统一维护在 `docs/protocols/`。
- 每次开始一轮新开发前，先把最新 `main` 同步到当前模块分支。
- 每完成一个阶段，就尽快把该模块分支合回 `main`，不要长期积压大量未合并提交。

## 3. Worktree 布局

推荐目录结构如下：

```text
robot_task/
  main 工作目录
  .worktrees/
    feature-web/
    feature-llm-decision-making/
    feature-robot-service/
    feature-perception-service/
```

推荐约定：

- 根目录工作区固定在 `main`
- 每个模块分支各自有独立 worktree
- 不要在错误 worktree 中修改代码
- 开始开发前先执行：

```bash
git branch --show-current
pwd
git worktree list
```

## 4. 标准开发节奏

长期模块分支的推荐节奏如下：

1. 进入对应模块的 worktree。
2. 拉取远端最新引用。
3. 把 `origin/main` 同步到当前模块分支。
4. 在该模块分支上继续开发和提交。
5. 跑该模块自己的测试。
6. 将该模块分支合回 `main`。
7. 如需发布，再推送 `main`。

这里补充一个术语约定：

- `commit` / “提交” 指提交到本地仓库
- `push` / “推送” 默认指推送到远程仓库 `origin`
- 如果文档中写“推送 `main`”，默认含义就是执行类似 `git push origin main` 的命令，而不是仅停留在本地

图上通常会呈现为：

```text
main  ──●────●────●────M────●────M────●──
          \         /            /
robot      ●──●──●─/────●───────/
llm          ●──●─/─────●───────/
perception     ●─────────●──────/
web            ●─────────●──────/
```

含义是：

- 各模块分支可以持续存在
- 每轮开发前先吸收一次 `main`
- 做完一段再合回 `main`
- 下一轮继续重复

## 5. 同步 `main` 的标准命令

进入某个模块 worktree 后，先执行：

```bash
git fetch origin
git checkout <feature-branch>
git merge origin/main
```

说明：

- 如果当前模块分支已经是 `main` 的祖先或与 `main` 线性可合，`git merge origin/main` 会是 fast-forward。
- 如果当前模块分支和 `main` 已经分别有新提交，`git merge origin/main` 会生成一次普通 merge。
- 不要长期不做这一步，否则后面回并 `main` 时冲突会集中爆发。

## 6. 什么时候应该同步 `main`

建议在以下时机同步：

- 每次开始新一轮开发前
- `main` 上刚合入别的模块重要改动后
- 共享协议文档有变化后
- 准备把当前模块分支合回 `main` 前

不要求机械地每天同步一次，但不要让模块分支长期脱离 `main`。

## 7. 四个模块的具体建议

### 7.1 `feature/web`

- 如果 `web` 还没有形成复杂历史，可以直接同步到最新 `main` 后继续开发。
- 如果未来 `web` 任务边界非常清楚，也可以从 `main` 临时新开 `feature/web-<topic>`，做完后再并回 `main`。

常用命令：

```bash
cd /Users/haitong/Code_ws/robot_task/.worktrees/feature-web
git fetch origin
git checkout feature/web
git merge origin/main
```

### 7.2 `feature/llm-decision-making`

- 这是长期决策模块开发通道。
- 每次继续开发前，先同步 `origin/main`。
- 修改时应尽量限制在 `llm_decision_making/` 目录和必要的共享协议文档。

常用命令：

```bash
cd /Users/haitong/Code_ws/robot_task/.worktrees/feature-llm-decision-making
git fetch origin
git checkout feature/llm-decision-making
git merge origin/main
```

### 7.3 `feature/robot-service`

- 这是长期机器人服务开发通道。
- 每次继续开发前，先同步 `origin/main`。
- 修改时应尽量限制在 `robot_service/` 目录和必要的共享协议文档。

常用命令：

```bash
cd /Users/haitong/Code_ws/robot_task/.worktrees/feature-robot-service
git fetch origin
git checkout feature/robot-service
git merge origin/main
```

### 7.4 `feature/perception-service`

- 这是长期感知模块开发通道。
- 如果该分支基线较老，第一次继续开发前，通常需要先把 `origin/main` 合进去，并处理一次共享文档或协议冲突。
- 如果该分支太旧、历史太乱，也可以直接从当前 `main` 新开一个新的感知分支，再把旧分支中真正需要的提交 `cherry-pick` 过去。

继续沿用旧分支时：

```bash
cd /Users/haitong/Code_ws/robot_task/.worktrees/feature-perception-service
git fetch origin
git checkout feature/perception-service
git merge origin/main
```

从当前 `main` 重开时：

```bash
cd /Users/haitong/Code_ws/robot_task
git worktree add .worktrees/feature-perception-service-next -b feature/perception-service-next main
```

## 8. 合回 `main` 的推荐方式

完成一个阶段后，推荐按下面步骤回并：

1. 确认当前模块分支已经同步过最新 `main`。
2. 跑该模块自己的测试。
3. 切回 `main` 工作目录。
4. 再次确认 `main` 工作树干净。
5. 将目标模块分支合入 `main`。
6. 必要时在合并后的 `main` 上再跑一轮相关测试。

常见命令：

```bash
cd /Users/haitong/Code_ws/robot_task
git checkout main
git fetch origin
git merge --ff-only origin/main
git merge --no-ff feature/<module-branch>
git push origin main
```

说明：

- 本地 `commit` 完成后，变更只进入本地仓库
- 只有执行 `git push origin <branch>` 后，远程仓库才会更新
- 本文档中凡是出现“推送”，若无特别说明，默认都是推送到远程仓库

如果当前需求同时改动多个模块，推荐先从 `main` 新建一个临时 integration 分支，把多个模块分支先合进去验证，再把 integration 分支合回 `main`。

## 9. 共享文档与协议冲突处理原则

当模块分支同步 `main` 或合回 `main` 时，优先按以下规则处理冲突：

- 本模块目录中的实现代码，以当前模块分支为主
- 其他无关模块目录，默认保留 `main`
- 仓库根目录 `README.md`、`AGENTS.md`、`docs/git_worktree_安排.md` 等仓库级文档，默认保留 `main`
- `docs/protocols/` 下的共享协议文档，只有在当前任务确实涉及接口边界变更时才修改

不要因为当前在某个模块分支上开发，就顺手把其他模块目录或仓库级文档改回旧状态。

## 10. 什么时候应该新开临时分支

虽然 4 个模块分支可以长期存在，但以下情况更适合从 `main` 临时新开分支：

- 一次任务边界非常清楚，且希望提交历史更干净
- 一次任务同时涉及两个模块，但不想污染单模块长期分支
- 某个旧模块分支历史已经太旧、太乱，不适合继续滚动开发

常见做法：

```bash
git worktree add .worktrees/feature-robot-service-<topic> -b feature/robot-service-<topic> main
```

做完后合回 `main`，再决定是否保留该临时分支。

## 11. 一句话总结

本仓库采用“`main` 作为唯一集成主线，4 个模块分支作为长期开发通道”的方式工作：

- 开发前先同步 `main`
- 开发时只改本模块
- 做完一段尽快合回 `main`
- 跨模块任务优先用临时 integration 分支
