from __future__ import annotations

import os


def _read_bool_env(env_name: str, default_value: bool) -> bool:
    raw_value = os.getenv(env_name)
    if raw_value is None:
        return default_value

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api-inference.modelscope.cn/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("MODELSCOPE_API_KEY", "ms-e5a7966a-0ee1-4614-81a4-3a2be725deb3"))
LLM_TRUST_ENV = _read_bool_env("LLM_TRUST_ENV", False)
