from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    robot_service_host: str
    robot_service_port: int
    isaac_sim_root: str | None
    runs_dir: Path
    log_level: str
    worker_start_timeout_s: float = 60.0
    worker_command_timeout_s: float = 10.0

    @classmethod
    def from_env(cls) -> "Settings":
        isaac_sim_root = os.getenv("ISAAC_SIM_ROOT")
        return cls(
            robot_service_host=os.getenv("ROBOT_SERVICE_HOST", "127.0.0.1"),
            robot_service_port=int(os.getenv("ROBOT_SERVICE_PORT", "8000")),
            isaac_sim_root=isaac_sim_root.strip() if isaac_sim_root else None,
            runs_dir=Path(os.getenv("RUNS_DIR", "robot_service/runs")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

