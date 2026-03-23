from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


Vec3 = tuple[float, float, float]
Vec2 = tuple[float, float]


@dataclass(frozen=True)
class RuntimeConfig:
    idle_sleep_s: float
    blocks_scene_stabilization_steps: int
    ycb_scene_stabilization_steps: int


@dataclass(frozen=True)
class TableConfig:
    root_prim_path: str
    top_prim_path: str
    center_position_xy_m: tuple[float, float]
    top_size_m: Vec3
    surface_height_m: float
    leg_thickness_m: float
    leg_inset_m: float
    top_color_rgb: Vec3
    leg_color_rgb: Vec3


@dataclass(frozen=True)
class FrankaConfig:
    prim_path: str
    usd_override_path: str | None
    asset_root_override_path: str | None
    asset_relative_path: str
    base_position_m: Vec3
    base_rotation_euler_deg: Vec3


@dataclass(frozen=True)
class CameraConfig:
    prim_path: str
    name: str
    position_m: Vec3
    rotation_euler_deg: Vec3
    focal_length_mm: float
    horizontal_aperture_mm: float
    vertical_aperture_mm: float
    clipping_range_m: tuple[float, float]


@dataclass(frozen=True)
class FrankaPhotoPoseConfig:
    enabled: bool
    apply_on_reset: bool
    joint_positions: tuple[float, ...]
    joint_velocities: tuple[float, ...]


@dataclass(frozen=True)
class CameraWorkspaceConfig:
    center_position_xy_m: Vec2
    view_size_xy_m: Vec2
    fit_camera_to_workspace: bool


@dataclass(frozen=True)
class DomeLightConfig:
    prim_path: str
    intensity: float
    color_rgb: Vec3
    exposure: float


@dataclass(frozen=True)
class DistantLightConfig:
    prim_path: str
    intensity: float
    color_rgb: Vec3
    angle_deg: float
    rotation_euler_deg: Vec3


@dataclass(frozen=True)
class BlockObjectConfig:
    name: str
    prim_path: str
    size_m: Vec3
    center_position_xy_m: tuple[float, float]
    color_rgb: Vec3


@dataclass(frozen=True)
class YCBObjectConfig:
    name: str
    prim_path: str
    usd_file_name: str
    center_position_xy_m: tuple[float, float]
    spawn_height_above_table_m: float
    rotation_euler_deg: Vec3


@dataclass(frozen=True)
class YCBSceneConfig:
    asset_root_dir: Path
    physics_subdir_name: str
    objects: tuple[YCBObjectConfig, ...]


RUNTIME_CONFIG = RuntimeConfig(
    idle_sleep_s=0.05,
    blocks_scene_stabilization_steps=5,
    ycb_scene_stabilization_steps=90,
)

TABLE_CONFIG = TableConfig(
    root_prim_path="/World/BaseEnvironment/Table",
    top_prim_path="/World/BaseEnvironment/Table/Top",
    center_position_xy_m=(0.0, 0.0),
    top_size_m=(1.20, 1.20, 0.04),
    surface_height_m=0.78,
    leg_thickness_m=0.06,
    leg_inset_m=0.08,
    top_color_rgb=(0.42, 0.30, 0.22),
    leg_color_rgb=(0.20, 0.20, 0.20),
)

FRANKA_CONFIG = FrankaConfig(
    prim_path="/World/Franka",
    usd_override_path=None,
    asset_root_override_path=None,
    asset_relative_path="/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd",
    base_position_m=(0.0, -0.58, TABLE_CONFIG.surface_height_m),
    base_rotation_euler_deg=(0.0, 0.0, 90.0),
)

FRANKA_PHOTO_POSE_CONFIG = FrankaPhotoPoseConfig(
    enabled=True,
    apply_on_reset=True,
    joint_positions=(0.0, -1.3, 0.0, -2.5, 0.0, 1.4, 0.8, 0.04, 0.04),
    joint_velocities=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
)

TOP_CAMERA_CONFIG = CameraConfig(
    prim_path="/World/TopCamera",
    name="top_camera",
    position_m=(0.0, 0.0, 1.85),
    rotation_euler_deg=(0.0, 0.0, 0.0),
    focal_length_mm=18.0,
    horizontal_aperture_mm=20.955,
    vertical_aperture_mm=15.2908,
    clipping_range_m=(0.01, 20.0),
)

TOP_CAMERA_WORKSPACE_CONFIG = CameraWorkspaceConfig(
    center_position_xy_m=(0.0, 0.0),
    view_size_xy_m=(0.90, 0.66),
    fit_camera_to_workspace=True,
)

DOME_LIGHT_CONFIG = DomeLightConfig(
    prim_path="/World/Lights/DomeLight",
    intensity=450.0,
    color_rgb=(1.0, 1.0, 1.0),
    exposure=0.0,
)

DISTANT_LIGHT_CONFIG = DistantLightConfig(
    prim_path="/World/Lights/KeyLight",
    intensity=1800.0,
    color_rgb=(1.0, 0.98, 0.95),
    angle_deg=0.5,
    rotation_euler_deg=(45.0, 0.0, 35.0),
)

BLOCKS_SCENE_OBJECTS: tuple[BlockObjectConfig, ...] = (
    BlockObjectConfig(
        name="red_block_left_front",
        prim_path="/World/DesktopScene/Blocks/RedBlockLeftFront",
        size_m=(0.055, 0.055, 0.055),
        center_position_xy_m=(-0.18, -0.08),
        color_rgb=(0.85, 0.10, 0.10),
    ),
    BlockObjectConfig(
        name="blue_block_right_front",
        prim_path="/World/DesktopScene/Blocks/BlueBlockRightFront",
        size_m=(0.055, 0.055, 0.055),
        center_position_xy_m=(0.18, -0.10),
        color_rgb=(0.15, 0.30, 0.90),
    ),
    BlockObjectConfig(
        name="red_block_left_back",
        prim_path="/World/DesktopScene/Blocks/RedBlockLeftBack",
        size_m=(0.055, 0.055, 0.055),
        center_position_xy_m=(-0.10, 0.16),
        color_rgb=(0.85, 0.10, 0.10),
    ),
    BlockObjectConfig(
        name="blue_block_right_back",
        prim_path="/World/DesktopScene/Blocks/BlueBlockRightBack",
        size_m=(0.055, 0.055, 0.055),
        center_position_xy_m=(0.14, 0.12),
        color_rgb=(0.15, 0.30, 0.90),
    ),
)

YCB_SCENE_CONFIG = YCBSceneConfig(
    asset_root_dir=Path("/root/Downloads/YCB"),
    physics_subdir_name="Axis_Aligned_Physics",
    objects=(
        YCBObjectConfig(
            name="cracker_box",
            prim_path="/World/DesktopScene/YCB/CrackerBox",
            usd_file_name="003_cracker_box.usd",
            center_position_xy_m=(-0.18, -0.08),
            spawn_height_above_table_m=0.08,
            rotation_euler_deg=(0.0, 0.0, 10.0),
        ),
        YCBObjectConfig(
            name="sugar_box",
            prim_path="/World/DesktopScene/YCB/SugarBox",
            usd_file_name="004_sugar_box.usd",
            center_position_xy_m=(0.16, -0.06),
            spawn_height_above_table_m=0.08,
            rotation_euler_deg=(0.0, 0.0, -18.0),
        ),
        YCBObjectConfig(
            name="tomato_soup_can",
            prim_path="/World/DesktopScene/YCB/TomatoSoupCan",
            usd_file_name="005_tomato_soup_can.usd",
            center_position_xy_m=(-0.08, 0.18),
            spawn_height_above_table_m=0.12,
            rotation_euler_deg=(0.0, 0.0, 0.0),
        ),
        YCBObjectConfig(
            name="mustard_bottle",
            prim_path="/World/DesktopScene/YCB/MustardBottle",
            usd_file_name="006_mustard_bottle.usd",
            center_position_xy_m=(0.15, 0.12),
            spawn_height_above_table_m=0.12,
            rotation_euler_deg=(0.0, 0.0, 24.0),
        ),
    ),
)
