from __future__ import annotations

# `TASK_PARSER_LLM_URL` 建议填写完整的 OpenAI 兼容接口地址，
# 例如: https://your-host/v1/chat/completions
TASK_PARSER_LLM_URL = "https://api-inference.modelscope.cn/v1"

# 例如: gpt-4.1-mini / qwen-max / 本地部署模型名
TASK_PARSER_LLM_MODEL = "Qwen/Qwen3.5-27B"

# 如果你的接口不需要鉴权，可以保持为空字符串。
TASK_PARSER_LLM_API_KEY = "ms-e5a7966a-0ee1-4614-81a4-3a2be725deb3"

# 请求超时时间，单位秒。
TASK_PARSER_LLM_TIMEOUT_S = 60.0

# task_parser 固定走低温采样，尽量提高稳定性。
TASK_PARSER_LLM_TEMPERATURE = 0.0
