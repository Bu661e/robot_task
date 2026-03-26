from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TaskDescription:
    task_id: str
    objects_env_id: str
    instruction: str


@dataclass(slots=True)
class ParsedTask:
    task_id: str
    object_texts: list[str]
