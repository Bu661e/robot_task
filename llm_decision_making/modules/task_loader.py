from __future__ import annotations

from pathlib import Path

from utils.yaml_loader import load_yaml_file
from .schemas import SourceTask


class TaskLoader:
    """Load task descriptions from CLI input or HTTP input."""

    def load_from_cli(self, task_file: Path, task_id: str) -> SourceTask:
        task_entries = self._read_task_entries(task_file)

        for task_entry in task_entries:
            if str(task_entry["task_id"]) == task_id:
                return SourceTask(
                    task_id=str(task_entry["task_id"]),
                    instruction=str(task_entry["instruction"]),
                )

        raise ValueError(f"Task ID '{task_id}' not found in {task_file}.")

    def load_from_http(self) -> None:
        raise NotImplementedError("HTTP task loading is not implemented yet.")

    def _read_task_entries(self, task_file: Path) -> list[dict[str, str]]:
        task_entries = load_yaml_file(task_file)

        if not isinstance(task_entries, list):
            raise ValueError("Task YAML must contain a list of task entries.")

        required_fields = {"task_id", "instruction"}
        normalized_entries: list[dict[str, str]] = []
        for task_entry in task_entries:
            if not isinstance(task_entry, dict):
                raise ValueError("Each task entry must be a mapping.")

            if "objects_env_id" in task_entry:
                raise ValueError("Task entry contains deprecated field: objects_env_id")

            missing_fields = required_fields - task_entry.keys()
            if missing_fields:
                missing_fields_text = ", ".join(sorted(missing_fields))
                raise ValueError(
                    f"Task entry is missing required fields: {missing_fields_text}"
                )

            normalized_entries.append(
                {
                    "task_id": str(task_entry["task_id"]),
                    "instruction": str(task_entry["instruction"]),
                }
            )

        return normalized_entries
