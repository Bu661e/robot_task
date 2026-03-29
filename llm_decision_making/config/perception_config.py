from __future__ import annotations

import os


def _read_bool_env(env_name: str, default_value: bool) -> bool:
    raw_value = os.getenv(env_name)
    if raw_value is None:
        return default_value

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


PERCEPTION_BASE_URL = os.getenv("PERCEPTION_BASE_URL", "http://127.0.0.1:8000")
PERCEPTION_TIMEOUT_S = float(os.getenv("PERCEPTION_TIMEOUT_S", "30.0"))
PERCEPTION_TRUST_ENV = _read_bool_env("PERCEPTION_TRUST_ENV", False)
