from __future__ import annotations

from pathlib import Path

from .schemas import TaskDescription


class TaskLoader:
    """Load task descriptions from CLI input or HTTP input."""

    def load_from_cli(self, yaml_file_path: Path) -> TaskDescription:
        pass

    def load_from_http(self, yaml_content: str) -> TaskDescription:
        pass

