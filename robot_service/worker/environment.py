from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EnvironmentRuntime:
    session_dir: Path | None = None
    simulation_app: object | None = None
    current_environment_id: str | None = None
    scene_assets: list[str] = field(default_factory=list)

    def load_environment(self, environment_id: str) -> None:
        self.current_environment_id = environment_id
        self.scene_assets = ["ground", "light", "block"]

    @property
    def robot_status(self) -> str:
        return "ready"

    @property
    def action_apis(self) -> list[str]:
        return ["robot.pick_and_place(pick_position, place_position, rotation=None)"]

