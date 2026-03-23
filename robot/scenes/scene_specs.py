from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BaseEnvironmentSpec:
    robot_name: str
    robot_prim_path: str
    camera_name: str
    camera_prim_path: str
    table_surface_height_m: float


@dataclass(frozen=True)
class DesktopSceneSpec:
    scene_id: str
    description: str
    object_prim_paths: tuple[str, ...]
    stabilization_steps: int
