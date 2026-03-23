from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from robot.config import (
    DOME_LIGHT_CONFIG,
    DISTANT_LIGHT_CONFIG,
    FRANKA_CONFIG,
    FRANKA_PHOTO_POSE_CONFIG,
    TABLE_CONFIG,
    TOP_CAMERA_CONFIG,
    TOP_CAMERA_WORKSPACE_CONFIG,
    CameraConfig,
    CameraWorkspaceConfig,
    DomeLightConfig,
    DistantLightConfig,
    FrankaConfig,
    FrankaPhotoPoseConfig,
    TableConfig,
    Vec3,
)
from robot.scenes.scene_specs import BaseEnvironmentSpec


class BaseEnvironmentBuilder:
    def build(self, world: Any) -> BaseEnvironmentSpec:
        import numpy as np
        from isaacsim.core.api.objects import FixedCuboid
        from isaacsim.core.prims import SingleArticulation
        from isaacsim.core.utils.stage import add_reference_to_stage, get_current_stage
        from pxr import Gf, UsdGeom, UsdLux

        table_config: TableConfig = TABLE_CONFIG
        franka_config: FrankaConfig = FRANKA_CONFIG
        franka_photo_pose_config: FrankaPhotoPoseConfig = FRANKA_PHOTO_POSE_CONFIG
        camera_config: CameraConfig = TOP_CAMERA_CONFIG
        camera_workspace_config: CameraWorkspaceConfig = TOP_CAMERA_WORKSPACE_CONFIG
        dome_light_config: DomeLightConfig = DOME_LIGHT_CONFIG
        key_light_config: DistantLightConfig = DISTANT_LIGHT_CONFIG

        world.scene.add_default_ground_plane()

        stage = get_current_stage()
        if stage is None:
            raise RuntimeError("当前 USD stage 不存在，无法创建基础环境。")

        UsdGeom.Xform.Define(stage, "/World/BaseEnvironment")
        UsdGeom.Xform.Define(stage, table_config.root_prim_path)
        UsdGeom.Xform.Define(stage, "/World/Lights")

        tabletop_position = (
            table_config.center_position_xy_m[0],
            table_config.center_position_xy_m[1],
            table_config.surface_height_m - table_config.top_size_m[2] / 2.0,
        )
        world.scene.add(
            FixedCuboid(
                prim_path=table_config.top_prim_path,
                name="table_top",
                position=np.array(tabletop_position),
                scale=np.array(table_config.top_size_m),
                color=np.array(table_config.top_color_rgb),
            )
        )

        leg_height_m = table_config.surface_height_m - table_config.top_size_m[2]
        if leg_height_m <= 0.0:
            raise ValueError("桌腿高度必须大于 0，请检查 robot/config.py 中的桌子配置。")

        half_length_m = table_config.top_size_m[0] / 2.0
        half_width_m = table_config.top_size_m[1] / 2.0
        leg_offset_x_m = half_length_m - table_config.leg_inset_m
        leg_offset_y_m = half_width_m - table_config.leg_inset_m
        leg_center_z_m = leg_height_m / 2.0
        leg_scale = (
            table_config.leg_thickness_m,
            table_config.leg_thickness_m,
            leg_height_m,
        )
        leg_positions = (
            (
                table_config.center_position_xy_m[0] - leg_offset_x_m,
                table_config.center_position_xy_m[1] - leg_offset_y_m,
                leg_center_z_m,
            ),
            (
                table_config.center_position_xy_m[0] + leg_offset_x_m,
                table_config.center_position_xy_m[1] - leg_offset_y_m,
                leg_center_z_m,
            ),
            (
                table_config.center_position_xy_m[0] - leg_offset_x_m,
                table_config.center_position_xy_m[1] + leg_offset_y_m,
                leg_center_z_m,
            ),
            (
                table_config.center_position_xy_m[0] + leg_offset_x_m,
                table_config.center_position_xy_m[1] + leg_offset_y_m,
                leg_center_z_m,
            ),
        )

        for index, leg_position in enumerate(leg_positions, start=1):
            leg_prim_path = f"{table_config.root_prim_path}/Leg{index}"
            world.scene.add(
                FixedCuboid(
                    prim_path=leg_prim_path,
                    name=f"table_leg_{index}",
                    position=np.array(leg_position),
                    scale=np.array(leg_scale),
                    color=np.array(table_config.leg_color_rgb),
                )
            )

        franka_asset_path = _resolve_franka_asset_path(franka_config)
        franka_placement_prim = UsdGeom.Xform.Define(stage, franka_config.prim_path)
        franka_asset_prim_path = f"{franka_config.prim_path}/Asset"
        add_reference_to_stage(
            usd_path=franka_asset_path,
            prim_path=franka_asset_prim_path,
        )
        franka_xform = UsdGeom.XformCommonAPI(franka_placement_prim)
        franka_xform.SetTranslate(Gf.Vec3d(*franka_config.base_position_m))
        franka_xform.SetRotate(Gf.Vec3f(*franka_config.base_rotation_euler_deg))
        franka_robot = world.scene.add(
            SingleArticulation(
                prim_path=franka_asset_prim_path,
                name="franka",
            )
        )
        _configure_franka_photo_pose(
            franka_robot,
            franka_photo_pose_config,
        )

        camera_prim = UsdGeom.Camera.Define(stage, camera_config.prim_path)
        camera_xform = UsdGeom.XformCommonAPI(camera_prim)
        camera_position_m: Vec3 = (
            camera_workspace_config.center_position_xy_m[0],
            camera_workspace_config.center_position_xy_m[1],
            camera_config.position_m[2],
        )
        camera_xform.SetTranslate(Gf.Vec3d(*camera_position_m))
        camera_xform.SetRotate(Gf.Vec3f(*camera_config.rotation_euler_deg))
        camera_focal_length_mm = _resolve_top_camera_focal_length_mm(
            camera_config,
            table_config,
            camera_workspace_config,
        )
        camera_prim.GetFocalLengthAttr().Set(camera_focal_length_mm)
        camera_prim.GetHorizontalApertureAttr().Set(camera_config.horizontal_aperture_mm)
        camera_prim.GetVerticalApertureAttr().Set(camera_config.vertical_aperture_mm)
        camera_prim.GetClippingRangeAttr().Set(Gf.Vec2f(*camera_config.clipping_range_m))

        dome_light_prim = UsdLux.DomeLight.Define(stage, dome_light_config.prim_path)
        dome_light_prim.CreateIntensityAttr(dome_light_config.intensity)
        dome_light_prim.CreateColorAttr(Gf.Vec3f(*dome_light_config.color_rgb))
        dome_light_prim.CreateExposureAttr(dome_light_config.exposure)

        key_light_prim = UsdLux.DistantLight.Define(stage, key_light_config.prim_path)
        key_light_prim.CreateIntensityAttr(key_light_config.intensity)
        key_light_prim.CreateColorAttr(Gf.Vec3f(*key_light_config.color_rgb))
        key_light_prim.CreateAngleAttr(key_light_config.angle_deg)
        key_light_xform = UsdGeom.XformCommonAPI(key_light_prim)
        key_light_xform.SetRotate(Gf.Vec3f(*key_light_config.rotation_euler_deg))

        base_environment_spec: BaseEnvironmentSpec = BaseEnvironmentSpec(
            robot_name="franka",
            robot_prim_path=franka_asset_prim_path,
            camera_name=camera_config.name,
            camera_prim_path=camera_config.prim_path,
            table_surface_height_m=table_config.surface_height_m,
        )
        return base_environment_spec


def _configure_franka_photo_pose(
    franka_robot: Any,
    franka_photo_pose_config: FrankaPhotoPoseConfig,
) -> None:
    import numpy as np

    if not franka_photo_pose_config.enabled:
        return

    joint_positions = np.array(franka_photo_pose_config.joint_positions, dtype=float)
    joint_velocities = np.array(franka_photo_pose_config.joint_velocities, dtype=float)
    if joint_positions.shape != joint_velocities.shape:
        raise ValueError(
            "robot/config.py 中的 FRANKA_PHOTO_POSE_CONFIG 关节位置与速度维度不一致。"
        )
    franka_robot.set_joints_default_state(
        positions=joint_positions,
        velocities=joint_velocities,
    )


def _resolve_top_camera_focal_length_mm(
    camera_config: CameraConfig,
    table_config: TableConfig,
    camera_workspace_config: CameraWorkspaceConfig,
) -> float:
    if not camera_workspace_config.fit_camera_to_workspace:
        return camera_config.focal_length_mm

    workspace_width_m = camera_workspace_config.view_size_xy_m[0]
    workspace_height_m = camera_workspace_config.view_size_xy_m[1]
    if workspace_width_m <= 0.0 or workspace_height_m <= 0.0:
        raise ValueError("顶视相机工作区尺寸必须大于 0，请检查 robot/config.py。")

    camera_height_above_table_m = camera_config.position_m[2] - table_config.surface_height_m
    if camera_height_above_table_m <= 0.0:
        raise ValueError("顶视相机高度必须高于桌面，请检查 robot/config.py。")

    focal_length_from_width_mm = (
        camera_height_above_table_m * camera_config.horizontal_aperture_mm / workspace_width_m
    )
    focal_length_from_height_mm = (
        camera_height_above_table_m * camera_config.vertical_aperture_mm / workspace_height_m
    )
    return min(focal_length_from_width_mm, focal_length_from_height_mm)


def _resolve_franka_asset_path(franka_config: FrankaConfig) -> str:
    if franka_config.usd_override_path is not None:
        override_path = franka_config.usd_override_path
        if _is_remote_asset_path(override_path):
            return override_path

        local_override_path = Path(override_path).expanduser()
        if not local_override_path.exists():
            raise FileNotFoundError(
                "robot/config.py 中配置的 FRANKA usd_override_path 不存在: "
                f"{local_override_path}"
            )
        return str(local_override_path)

    candidate_paths: list[str] = []
    if franka_config.asset_root_override_path is not None:
        candidate_paths.append(
            _join_asset_root_path(
                franka_config.asset_root_override_path,
                franka_config.asset_relative_path,
            )
        )

    assets_root_path = _get_isaac_assets_root_path()
    if assets_root_path is not None:
        candidate_paths.append(
            _join_asset_root_path(
                assets_root_path,
                franka_config.asset_relative_path,
            )
        )

    for candidate_path in candidate_paths:
        if _is_remote_asset_path(candidate_path):
            return candidate_path
        if Path(candidate_path).expanduser().exists():
            return candidate_path

    candidate_text = ", ".join(str(path) for path in candidate_paths) or "无可用候选路径"
    raise FileNotFoundError(
        "未找到 Franka USD 资产。请在 robot/config.py 中填写 usd_override_path "
        "或 asset_root_override_path。当前候选路径: "
        f"{candidate_text}"
    )


def _get_isaac_assets_root_path() -> str | None:
    try:
        from isaacsim.storage.native import get_assets_root_path
    except Exception:
        return None

    try:
        assets_root_path = get_assets_root_path()
    except Exception:
        return None

    if not assets_root_path:
        return None
    return str(assets_root_path)


def _join_asset_root_path(asset_root_path: str, asset_relative_path: str) -> str:
    normalized_root_path = asset_root_path.rstrip("/")
    normalized_relative_path = asset_relative_path.lstrip("/")
    if _is_remote_asset_path(normalized_root_path):
        return f"{normalized_root_path}/{normalized_relative_path}"
    return str(Path(normalized_root_path).expanduser() / normalized_relative_path)


def _is_remote_asset_path(asset_path: str) -> bool:
    parsed = urlparse(asset_path)
    return parsed.scheme in {"http", "https", "omniverse"}
