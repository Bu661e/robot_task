# AGENTS

## 开发环境设置

- 语言：Python
- API 层包管理：uv
- API 层启动环境：`source .venv/bin/activate`
- API 层启动命令：`cd perception_service && .venv/bin/uvicorn app:app --reload`
- 模型环境：
  - `SAM3` 使用 conda 环境 `sam3`
  - `SAM3D-object` 使用 conda 环境 `sam3d-objects`
- 当前机器上的权重入口固定约定：
  - `perception_service/sam3-ultralytics/sam3.pt -> /root/sam3.pt`
  - `perception_service/SAM3D-object/checkpoints/hf -> /root/hf`

## 文档

- 本模块的详细设计说明优先参考 `README.md`。
- 进程边界、环境路径、权重软链接约定优先参考 `docs/进程与环境说明.md`。
- `SAM3` 和 `SAM3D-object` 的本地接入说明分别参考：
  - `docs/ultralytics_SAM3_使用指南.md`
  - `docs/SAM3D-object_使用指南.md`
- 跨模块共享协议文档统一放在仓库根目录 `docs/protocols/`，当前主要是 `docs/protocols/llm_decision_making__perception_service.md`。
- `perception_service/docs/` 目录只放本模块内部说明，不要把共享协议文档重新复制一份到这里。

## 编码规范

### 文件组织

- 推荐按职责划分文件：
  - `app.py`：`uvicorn` 启动入口
  - `api/app.py`：FastAPI 应用工厂和异常处理注册
  - `api/routers/`：HTTP 路由层，只负责入参接收和依赖注入
  - `api/services/`：核心业务逻辑，包括 artifact 管理、pointmap 生成、后端调度和推理编排
  - `api/schemas.py`：本模块对外协议和内部编排依赖的数据结构
  - `api/settings.py`：运行目录、模型解释器路径、桥接脚本路径
  - `backend_scripts/`：调用 `SAM3D-object` 这类外部模型环境的桥接脚本
  - `sam3-ultralytics/`：`SAM3` 的仓库内接入层
  - `docs/`：本模块内部说明文档
- 新增代码时先判断归属：HTTP 入口放 `routers/`，主编排放 `services/`，协议结构放 `schemas.py`，外部模型桥接放 `backend_scripts/` 或 `sam3-ultralytics/`。
- `SAM3D-object/` 是本地上游仓库 checkout，不要把当前模块自己的 API 编排逻辑塞到上游仓库目录里。
- 新增跨模块接口协议文档时，统一放到仓库根目录 `docs/protocols/`，不要放到 `perception_service/docs/`。

### 模块边界

- `pointmap` 固定在 `perception_service` 内部生成，不作为跨模块上传字段暴露。
- API 层 `.venv` 只放轻量依赖，不要把 `ultralytics`、`torch`、`pytorch3d`、`flash_attn`、`kaolin` 等重依赖直接装进来。
- `SAM3` 和 `SAM3D-object` 一律通过子进程桥接，不要让 FastAPI 进程直接耦合它们的环境初始化逻辑。
- 没有明确需求时，不要顺手修改 `llm_decision_making`、`robot_service` 或共享协议之外的其他模块代码。
- 如果确实要修改协议字段，先同步 `schemas.py`、`README.md` 和仓库根目录协议文档。

### 命名约定

- Python 模块文件、函数、变量使用 `snake_case`。
- 类、`dataclass`、Pydantic schema 使用 `PascalCase`。
- 常量、环境变量、错误码使用 `UPPER_SNAKE_CASE`。
- HTTP 请求和响应字段统一使用协议中的 `snake_case` 命名，不要混入别的风格。
- 位姿字段统一使用 `quaternion_wxyz`，不要再引入旧四元数字段名。

### 类型标注

- 新增或修改代码时，只要能够明确判断数据类型，就应显式补全类型标注。
- 函数参数、返回值、类属性、`dataclass` 字段尽量补全类型。
- 对外协议结构优先使用 Pydantic schema，不要把结构化请求和响应长期保持为裸 `dict`。
- 如果某段数据结构已经在协议或 README 中定义，就按既有 schema 实现，不要再临时发明另一套字段。

### 错误处理与 artifact

- API 层错误统一优先走 `ApiError`，保持 `error_code`、`message`、`ext` 结构一致。
- artifact 类型必须严格复用协议里已定义的枚举值。
- 图片、点云、mesh、debug 数据等大内容不要直接塞到日志文本或响应摘要里，优先落成 artifact。
- 需要保留调试信息时，优先写 `debug_json` artifact，不要把大段原始 JSON 直接打印到终端。
- 修改模型调用路径、权重入口或软链接约定时，必须同步更新 `README.md` 和 `docs/进程与环境说明.md`。

### 测试

- 测试统一使用 `pytest`。
- 优先覆盖：
  - schema 校验
  - artifact 上传与读取
  - 深度图到 `pointmap` 的纯逻辑转换
  - `inference_service` 的 preflight 和错误路径
- 默认测试不要依赖真实 GPU 推理结果；`SAM3` / `SAM3D-object` 的默认测试优先 mock 子进程 JSON 输出。
- 如果做真实 GPU smoke test，单独说明运行条件，不要让它变成每次默认必跑测试。
- 每次修改后，至少运行与本次改动直接相关的测试。

### 审查

- 采用轻量自审，不要求正式多人 code review 流程。
- 自审重点包括：
  - 是否破坏 API 层与模型环境的边界
  - 是否把 `pointmap` 或重依赖错误地扩散到协议外
  - schema、错误码和 artifact 类型是否保持一致
  - `README.md`、环境说明和协议文档是否同步
  - 权重路径和软链接约定是否被误改

### Git提交

- 提交的 message 用中文
- 在本地仓库提交后直接推送到远程

## 开发时注意事项

- 在编写模块代码前，先检查 `README.md` 与当前任务是否一致；如果不一致，先问我应该改 README 还是改任务。
- 在编写协议相关代码前，先检查仓库根目录 `docs/protocols/llm_decision_making__perception_service.md` 是否与当前任务一致；如果不一致，先问我应该改协议还是改任务。
- 在改模型调用链路前，先检查 `docs/进程与环境说明.md`，确认 conda 环境名、解释器路径和权重软链接约定没有漂移。
- 对于每个新增输入输出结构，先设计 schema，再写入文档，然后在代码里实现。
- 我开发时通常按数据流顺序推进；如果你要改变开发顺序，先明确说明。
- 当开始一块新的子功能时，先写出简短开发计划，再开始改代码。

## 额外要求

- 当你有任何不清楚的地方，或是我没有表达清楚的地方，请先问我，不要自己猜着写。
- 如果你实现了某个模块或数据结构，记得回头补 `README.md` 和相关说明文档。
- 当你觉得该 git 提交了就提醒我。
- 禁止使用 subagent；如果一定要使用，先询问我。
