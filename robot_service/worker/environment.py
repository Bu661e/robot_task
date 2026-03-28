from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EnvironmentRuntime:
    session_dir: Path | None = None
    simulation_app: object | None = None
    current_environment_id: str | None = None
    scene_assets: list[str] = field(default_factory=list)
    world: object | None = None

    def load_environment(self, environment_id: str) -> None:
        if self.simulation_app is None:
            self._load_placeholder_scene()
        else:
            self._load_isaac_scene(environment_id)
        self.current_environment_id = environment_id

    def _load_placeholder_scene(self) -> None:
        self.world = None
        self.scene_assets = ["ground", "light", "block"]

    def _load_isaac_scene(self, environment_id: str) -> None:
        del environment_id  # Environment presets are still a follow-up; cloud bring-up uses one minimal scene.

        import numpy as np
        from isaacsim.core.api.objects import DynamicCuboid
        from isaacsim.core.api.world import World
        from isaacsim.core.utils.stage import create_new_stage, get_current_stage
        from pxr import Sdf, UsdLux

        World.clear_instance()
        create_new_stage()
        world = World(stage_units_in_meters=1.0)
        try:
            world.scene.add_default_ground_plane()

            stage = get_current_stage()
            light = UsdLux.DistantLight.Define(stage, Sdf.Path("/World/KeyLight"))
            light.CreateIntensityAttr(500.0)

            world.scene.add(
                DynamicCuboid(
                    prim_path="/World/Block",
                    name="block",
                    position=np.array([0.0, 0.0, 0.1]),
                    size=0.2,
                    color=np.array([0.2, 0.6, 0.9]),
                )
            )
            world.reset()
        except Exception:
            World.clear_instance()
            raise

        self.world = world
        self.scene_assets = ["ground", "light", "block"]

    @property
    def robot_status(self) -> str:
        return "ready"

    @property
    def action_apis(self) -> list[str]:
        return ["robot.pick_and_place(pick_position, place_position, rotation=None)"]
