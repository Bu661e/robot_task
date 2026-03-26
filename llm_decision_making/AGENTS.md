# AGENTS


## 开发环境设置 

-   语言：Python
-   包管理：uv
-   启动环境：`source .venv/bin/activate`

## 文档

- 本模块的详细设计说明优先参考 `README.md`。
- 协议文档放在 `docs/` 目录，包含与 `robot_service`、`perception_service` 的 HTTP 交互协议说明，以及模块内部使用的数据结构定义。

## 编码规范

### 文件组织

- 推荐按职责划分文件：
  - `main.py`：主流程入口，负责串联任务读取、感知调用、策略生成和执行调度。
  - `docs/`：协议文档，包含与 `robot_service`、`perception_service` 的 HTTP 交互协议说明，以及模块内部使用的数据结构定义。
  - `modules/`：核心业务模块，每个文件只负责一个明确职责
    - `schemas.py`：定义本模块所有使用的数据结构和 Schema 类型
  - `config/`：配置和静态资源，包含需要手动填写或环境相关的参数，以及 prompt、任务样例等配置文件。
  - `utils/`：通用辅助逻辑，放与单个业务模块弱耦合的工具函数，不要把主流程编排塞进这里。
- 新增代码时先判断归属：业务编排放 `modules/`，配置放 `config/`，通用工具放 `utils/`；如果一个文件开始同时承担协议、决策、执行等多种职责，优先继续拆分。

### 命名约定

- Python 模块文件、函数、变量使用 `snake_case`，例如 `task_parser.py`、`load_task_file()`。
- 类、`dataclass`、Schema 类型使用 `PascalCase`，例如 `TaskRequest`、`ParsedTask`。
- 常量、环境变量名使用 `UPPER_SNAKE_CASE`。
- 配置文件名尽量与模块名对应，采用 `snake_case`，例如 `modules/task_parser.py` 对应 `config/task_parser_config.py`。
- HTTP 请求体、响应体中的字段名优先保持一致的 `snake_case` 风格，避免在模块间混用多套命名规则。

### 类型标注

- 新增或修改代码时，只要能够明确判断数据类型，就应显式写出类型标注，不要省略。
- 函数参数、返回值、类属性、`dataclass` 字段等，尽量补全类型信息。
- 函数入参类型应保持固定明确；如果参数是必需的，不要写成 `Type | None = None`、`Optional[Type] = None` 这类可空且带默认值的形式。
- 结构化数据不要传裸 `dict`。
- 在类型暂时无法确定，询问我，按理来说不会出现这种情况。


### 日志

- 使用 Python 标准库 `logging` 模块，配置日志同时输出到终端和文件。
- 每次执行任务时，都要在固定目录 `runs/` 下创建一个以时间戳命名的子目录，例如 `runs/2023-10-01_12-00-00_task-<task_id>`，保存本次任务的全部日志和产物。
- 日志必须同时输出到终端和文件；当前任务目录中至少包含 `run.log`、`requests/`、`responses/`、`artifacts/`。
- 日志内容应覆盖模块之间流转的关键数据、HTTP 请求与响应摘要，以及异常信息。
- 如果响应中包含图片、文件、点云、mask、深度图等内容，必须额外保存到 `artifacts/`，日志中只记录摘要和文件路径，不直接打印大块原始内容。

### 测试

- 测试统一使用 `pytest`。
- 优先覆盖纯逻辑模块和主流程 smoke test。
- 涉及 `robot_service`、`perception_service` 的测试优先 mock HTTP 响应，不依赖真实远端服务。
- 每次修改后，至少运行与本次改动直接相关的测试。

### 审查

- 采用轻量自审，不要求正式多人 code review 流程。
- 自审重点包括：是否破坏模块边界、是否硬编码配置、类型和 Schema 是否清楚、日志是否补全、`README.md` 和协议文档是否同步。
- 关键改动完成后，如有需要，可再补一次 Codex review。

### Git提交
- 提交时记得记录本次提交来自 llm_decision_making 模块, 再使用 git-commit skill
  - "llm_decision_making: {xxx}" 其中 xxx 是使用 git-commit skill得到本次提交的简要说明



## 开发时注意事项
- 在编写模块代码前，先检查 `README.md` 与当前任务是否一致，如果不一致询问是否更改`README`或更改任务。
- 在编写接口协议代码前，先检查 `docs/对应接口文档` 与当前任务是否一致，如果不一致询问是否更改`docs/对应接口文档`或更改任务。
- 对于每个模块的输入和输出，应该设计一个Schema，如果文档中没有设计，请设计好让我检查，之后在写入文档，并且在代码中实现这个Schema。
- 我在开发时，是按照数据传输顺序，虽然有时候会考虑后面流程代码复用，但是不会突然从前面转到后面
- 当开始一个新模块编写时，使用writing-plans skill，写出开发计划

  
## 额外要求
- 当你有任何不清楚的地方，或是我没有表达清楚的地方，请务必先问我，而不是自己猜测着写代码。
- 当前 README 中内容还不完整，或是我对于其中具体内容还是模糊的。等实现完某个模块或数据结构时候，需要回过头来完善 README 中对应的内容
- 当你觉得该git提交了就提醒我
- 如果需要某一个小任务可以使用subagent的话，就使用

