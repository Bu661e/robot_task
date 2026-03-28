from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class BackendCommand:
    name: str
    python_path: Path
    script_path: Path

    def probe(self) -> dict[str, Any]:
        return {
            "python_path": str(self.python_path),
            "python_exists": self.python_path.is_file(),
            "script_path": str(self.script_path),
            "script_exists": self.script_path.is_file(),
        }

    def invoke_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.python_path.is_file() or not self.script_path.is_file():
            return {
                "status": "unavailable",
                **self.probe(),
            }

        process = subprocess.run(
            [str(self.python_path), str(self.script_path)],
            input=json.dumps(payload, ensure_ascii=True),
            capture_output=True,
            text=True,
            check=False,
        )

        if process.returncode != 0:
            return {
                "status": "failed",
                "returncode": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
                **self.probe(),
            }

        try:
            response = json.loads(process.stdout or "{}")
        except json.JSONDecodeError:
            return {
                "status": "invalid_output",
                "stdout": process.stdout,
                "stderr": process.stderr,
                **self.probe(),
            }

        return {
            "status": "ok",
            "response": response,
            **self.probe(),
        }
