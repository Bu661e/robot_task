from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class TaskDescription:
    task_id: str
    objects_env_id: str
    instruction: str
    raw_yaml: str


@dataclass(slots=True)
class ParsedTask:
    task_id: str
    object_texts: list[str]

