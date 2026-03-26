from __future__ import annotations

from typing import Any

from robot_service.config import (
    BLOCKS_SCENE_OBJECTS,
    RUNTIME_CONFIG,
    RuntimeConfig,
)
from robot_service.scenes.scene_specs import BaseEnvironmentSpec, DesktopSceneSpec


class BlocksDesktopSceneBuilder:
    scene_id = "blocks_scene"

    def build(
        self,
        world: Any,
        base_environment: BaseEnvironmentSpec,
    ) -> DesktopSceneSpec:
        import numpy as np
        from isaacsim.core.api.objects import FixedCuboid
        from isaacsim.core.utils.stage import get_current_stage
        from pxr import UsdGeom

        runtime_config: RuntimeConfig = RUNTIME_CONFIG
        stage = get_current_stage()
        if stage is None:
            raise RuntimeError("当前 USD stage 不存在，无法创建 blocks_scene。")
        UsdGeom.Xform.Define(stage, "/World/DesktopScene")
        UsdGeom.Xform.Define(stage, "/World/DesktopScene/Blocks")

        object_prim_paths: list[str] = []
        for block_config in BLOCKS_SCENE_OBJECTS:
            block_position = (
                block_config.center_position_xy_m[0],
                block_config.center_position_xy_m[1],
                base_environment.table_surface_height_m + block_config.size_m[2] / 2.0,
            )
            world.scene.add(
                FixedCuboid(
                    prim_path=block_config.prim_path,
                    name=block_config.name,
                    position=np.array(block_position),
                    scale=np.array(block_config.size_m),
                    color=np.array(block_config.color_rgb),
                )
            )
            object_prim_paths.append(block_config.prim_path)

        desktop_scene_spec: DesktopSceneSpec = DesktopSceneSpec(
            scene_id=self.scene_id,
            description="红蓝方块桌面环境，固定 2 红 2 蓝布局。",
            object_prim_paths=tuple(object_prim_paths),
            stabilization_steps=runtime_config.blocks_scene_stabilization_steps,
        )
        return desktop_scene_spec
