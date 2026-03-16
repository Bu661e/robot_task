from __future__ import annotations

from typing import Any


class RobotBridge:
    def capture_frame(self) -> tuple[dict[str, Any], dict[str, Any], Any]:
        raise NotImplementedError

    def shutdown(self) -> None:
        raise NotImplementedError
