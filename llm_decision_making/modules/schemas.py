from __future__ import annotations

from dataclasses import dataclass




@dataclass(slots=True)
class SourceTask:
    task_id: str
    instruction: str


@dataclass(slots=True)
class ParsedTask:
    task_id: str
    instruction: str
    object_texts: list[str]
