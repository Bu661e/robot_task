from __future__ import annotations

import os


def _read_bool_env(env_name: str, default_value: bool) -> bool:
    raw_value = os.getenv(env_name)
    if raw_value is None:
        return default_value

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


ROBOT_BASE_URL = os.getenv("ROBOT_BASE_URL", "http://127.0.0.1:8000")
ROBOT_BACKEND_TYPE = os.getenv("ROBOT_BACKEND_TYPE", "isaac_sim")
ROBOT_TIMEOUT_S = float(os.getenv("ROBOT_TIMEOUT_S", "30.0"))
ROBOT_TRUST_ENV = _read_bool_env("ROBOT_TRUST_ENV", False)
