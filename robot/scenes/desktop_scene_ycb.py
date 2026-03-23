from __future__ import annotations

from typing import Any

from robot.config import (
    RUNTIME_CONFIG,
    YCB_SCENE_CONFIG,
    RuntimeConfig,
    YCBSceneConfig,
)
from robot.scenes.scene_specs import BaseEnvironmentSpec, DesktopSceneSpec


class YCBDesktopSceneBuilder:
    scene_id = "ycb_scene"

    def build(
        self,
        world: Any,
        base_environment: BaseEnvironmentSpec,
    ) -> DesktopSceneSpec:
        from isaacsim.core.utils.stage import add_reference_to_stage, get_current_stage
        from pxr import Gf, UsdGeom

        runtime_config: RuntimeConfig = RUNTIME_CONFIG
        ycb_scene_config: YCBSceneConfig = YCB_SCENE_CONFIG

        stage = get_current_stage()
        if stage is None:
            raise RuntimeError("当前 USD stage 不存在，无法创建 ycb_scene。")
        UsdGeom.Xform.Define(stage, "/World/DesktopScene")
        UsdGeom.Xform.Define(stage, "/World/DesktopScene/YCB")

        scene_asset_dir = ycb_scene_config.asset_root_dir / ycb_scene_config.physics_subdir_name
        if not scene_asset_dir.exists():
            raise FileNotFoundError(
                "YCB physics 资产目录不存在，请检查 robot/config.py: "
                f"{scene_asset_dir}"
            )

        object_prim_paths: list[str] = []
        for object_config in ycb_scene_config.objects:
            usd_path = scene_asset_dir / object_config.usd_file_name
            if not usd_path.exists():
                raise FileNotFoundError(
                    "YCB USD 文件不存在，请检查 robot/config.py: "
                    f"{usd_path}"
                )

            placement_prim = UsdGeom.Xform.Define(stage, object_config.prim_path)
            asset_prim_path = f"{object_config.prim_path}/Asset"
            add_reference_to_stage(
                usd_path=str(usd_path),
                prim_path=asset_prim_path,
            )
            object_xform = UsdGeom.XformCommonAPI(placement_prim)
            object_xform.SetTranslate(
                Gf.Vec3d(
                    object_config.center_position_xy_m[0],
                    object_config.center_position_xy_m[1],
                    base_environment.table_surface_height_m
                    + object_config.spawn_height_above_table_m,
                )
            )
            object_xform.SetRotate(Gf.Vec3f(*object_config.rotation_euler_deg))
            object_prim_paths.append(object_config.prim_path)

        desktop_scene_spec: DesktopSceneSpec = DesktopSceneSpec(
            scene_id=self.scene_id,
            description="YCB 桌面环境，加载 4 个带 physics 的 Axis Aligned 物体。",
            object_prim_paths=tuple(object_prim_paths),
            stabilization_steps=runtime_config.ycb_scene_stabilization_steps,
        )
        return desktop_scene_spec
