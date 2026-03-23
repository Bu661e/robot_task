from __future__ import annotations

from robot.scenes.base_environment import BaseEnvironmentBuilder
from robot.scenes.desktop_scene_blocks import BlocksDesktopSceneBuilder
from robot.scenes.desktop_scene_ycb import YCBDesktopSceneBuilder
from robot.scenes.scene_specs import BaseEnvironmentSpec, DesktopSceneSpec

DesktopSceneBuilder = BlocksDesktopSceneBuilder | YCBDesktopSceneBuilder


def get_supported_scene_ids() -> tuple[str, ...]:
    return ("default_scene", "blocks_scene", "ycb_scene")


def get_desktop_scene_builder(scene_id: str) -> DesktopSceneBuilder:
    if scene_id in {"default_scene", BlocksDesktopSceneBuilder.scene_id}:
        return BlocksDesktopSceneBuilder()
    if scene_id == YCBDesktopSceneBuilder.scene_id:
        return YCBDesktopSceneBuilder()
    supported_scene_ids = ", ".join(get_supported_scene_ids())
    raise ValueError(
        f"未知的 scene_id: {scene_id}。当前支持: {supported_scene_ids}"
    )
