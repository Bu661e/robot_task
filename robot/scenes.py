from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BaseEnvironmentSpec:
    robot_name: str
    robot_prim_path: str
    camera_name: str
    camera_prim_path: str


@dataclass(frozen=True)
class DesktopSceneSpec:
    scene_id: str
    description: str


class BaseEnvironmentBuilder:
    def build(self, world: Any) -> BaseEnvironmentSpec:
        world.scene.add_default_ground_plane()
        # TODO: 在 Isaac Sim 5.0.0 环境中补齐固定桌面、Franka、相机和灯光。
        return BaseEnvironmentSpec(
            robot_name="franka",
            robot_prim_path="/World/Franka",
            camera_name="top_camera",
            camera_prim_path="/World/TopCamera",
        )


class DefaultDesktopSceneBuilder:
    scene_id = "default_scene"

    def build(self, world: Any) -> DesktopSceneSpec:
        _ = world
        # TODO: 参考 example/ 中的随机方块逻辑，替换成项目自己的桌面物体配置。
        return DesktopSceneSpec(
            scene_id=self.scene_id,
            description="默认桌面场景，占位实现，待补充具体物体布局。",
        )


def get_desktop_scene_builder(scene_id: str) -> DefaultDesktopSceneBuilder:
    if scene_id == DefaultDesktopSceneBuilder.scene_id:
        return DefaultDesktopSceneBuilder()
    raise ValueError(f"未知的 scene_id: {scene_id}")
