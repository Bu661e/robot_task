from __future__ import annotations

from datetime import datetime, timezone
from secrets import token_hex


def _utc_timestamp() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")


def new_session_id(backend_type: str) -> str:
    return f"sess_{backend_type}_{_utc_timestamp()}_{token_hex(2)}"


def new_session_task_id() -> str:
    return f"task_{_utc_timestamp()}_{token_hex(2)}"


def new_artifact_id(artifact_type: str, session_id: str) -> str:
    return f"artifact_{artifact_type}_{session_id}_{token_hex(2)}"

