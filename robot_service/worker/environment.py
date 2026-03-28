from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import random
from typing import Any

from robot_service.common.schemas import (
    ArtifactRecord,
    ArtifactRef,
    CameraExtrinsics,
    CameraIntrinsics,
    CameraPayload,
)
from robot_service.runtime.ids import new_artifact_id
from robot_service.runtime.paths import get_artifact_path
from robot_service.worker.tabletop_layouts import TabletopLayoutContext, load_tabletop_layout


_TABLE_SIZE_M = 1.5
_TABLE_TOP_Z_M = _TABLE_SIZE_M
_TABLE_CENTER_Z_M = _TABLE_SIZE_M / 2.0
_TABLE_POSITION_XYZ = (0.0, 0.0, _TABLE_CENTER_Z_M)
_TABLE_COLOR_RGB = (0.56, 0.46, 0.36)
_ROBOT_POSITION_XYZ = (0.0, -0.6, _TABLE_TOP_Z_M)
_TOP_CAMERA_HEIGHT_M = 6.0
_OVERVIEW_CAMERA_POSITION_XYZ = (0.0, 3.3, 3.3)
_OVERVIEW_CAMERA_EULER_XYZ_DEG = (-60.0, 0.0, -180.0)
_CAMERA_RESOLUTION = (640, 640)
_TOP_CAMERA_ID = "table_top"
_TOP_CAMERA_PRIM_PATH = "/World/Cameras/TableTopCamera"
_OVERVIEW_CAMERA_ID = "table_overview"
_OVERVIEW_CAMERA_PRIM_PATH = "/World/Cameras/TableOverviewCamera"
_CAMERA_HORIZONTAL_APERTURE_M = 0.024
_CAMERA_FOCAL_LENGTH_M = 0.020
_SCENE_WARMUP_STEPS = 8
_KEY_LIGHT_INTENSITY = 650.0


@dataclass(frozen=True)
class CameraMountSpec:
    camera_id: str
    prim_path: str
    position_xyz: tuple[float, float, float]
    mode: str
    euler_xyz_deg: tuple[float, float, float] | None = None
    euler_extrinsic: bool = True
    camera_axes: str = "world"
    use_local_pose: bool = False


@dataclass
class EnvironmentRuntime:
    session_dir: Path | None = None
    simulation_app: object | None = None
    current_environment_id: str | None = None
    scene_assets: list[str] = field(default_factory=list)
    world: object | None = None
    cameras: dict[str, object] = field(default_factory=dict)
    robot: object | None = None
    table: object | None = None
    tabletop_object_ids: list[str] = field(default_factory=list)

    def load_environment(self, environment_id: str) -> None:
        if self.simulation_app is None:
            self._load_placeholder_scene(environment_id)
        else:
            self._load_isaac_scene(environment_id)
        self.current_environment_id = environment_id

    def _load_placeholder_scene(self, environment_id: str) -> None:
        layout = load_tabletop_layout(
            environment_id,
            rng=random.Random(),
            context=TabletopLayoutContext(table_size_m=_TABLE_SIZE_M, table_top_z_m=_TABLE_TOP_Z_M),
        )
        self.world = None
        self.cameras = {}
        self.robot = None
        self.table = None
        self.tabletop_object_ids = [spec.object_id for spec in layout]
        self.scene_assets = self._build_scene_assets(self.tabletop_object_ids)

    def _load_isaac_scene(self, environment_id: str) -> None:
        import isaacsim.core.utils.numpy.rotations as rot_utils
        import numpy as np
        from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid
        from isaacsim.core.api.world import World
        from isaacsim.core.utils.stage import create_new_stage, get_current_stage
        from isaacsim.robot.manipulators.examples.franka import Franka
        from isaacsim.sensors.camera import Camera
        from pxr import Sdf, UsdLux

        layout = load_tabletop_layout(
            environment_id,
            rng=random.Random(),
            context=TabletopLayoutContext(table_size_m=_TABLE_SIZE_M, table_top_z_m=_TABLE_TOP_Z_M),
        )

        World.clear_instance()
        create_new_stage()
        world = World(stage_units_in_meters=1.0)
        cameras: dict[str, object] = {}
        try:
            world.scene.add_default_ground_plane()

            stage = get_current_stage()
            key_light = UsdLux.DistantLight.Define(stage, Sdf.Path("/World/Lights/KeyLight"))
            key_light.CreateIntensityAttr(_KEY_LIGHT_INTENSITY)

            table = world.scene.add(
                FixedCuboid(
                    prim_path="/World/Furniture/Table",
                    name="table",
                    position=np.array(_TABLE_POSITION_XYZ),
                    scale=np.array([_TABLE_SIZE_M, _TABLE_SIZE_M, _TABLE_SIZE_M]),
                    size=1.0,
                    color=np.array(_TABLE_COLOR_RGB),
                )
            )
            robot = world.scene.add(
                Franka(
                    prim_path="/World/Franka",
                    name="franka",
                    position=np.array(_ROBOT_POSITION_XYZ),
                    orientation=rot_utils.euler_angles_to_quats(np.array([0.0, 0.0, 90.0]), degrees=True),
                )
            )

            tabletop_object_ids: list[str] = []
            for spec in layout:
                world.scene.add(
                    DynamicCuboid(
                        prim_path=f"/World/Tabletop/{spec.object_id}",
                        name=spec.object_id,
                        position=np.array(spec.position_xyz),
                        scale=np.array([spec.size_m, spec.size_m, spec.size_m]),
                        size=1.0,
                        color=np.array(spec.color_rgb),
                    )
                )
                tabletop_object_ids.append(spec.object_id)

            for camera_spec in self._camera_mount_specs():
                if camera_spec.euler_xyz_deg is not None:
                    orientation = rot_utils.euler_angles_to_quats(
                        np.array(camera_spec.euler_xyz_deg),
                        degrees=True,
                        extrinsic=camera_spec.euler_extrinsic,
                    )
                else:
                    raise RuntimeError(f"Camera spec {camera_spec.camera_id} is missing orientation data.")
                camera = world.scene.add(
                    Camera(
                        prim_path=camera_spec.prim_path,
                        name=camera_spec.camera_id,
                        resolution=_CAMERA_RESOLUTION,
                    )
                )
                if camera_spec.use_local_pose:
                    camera.set_local_pose(
                        translation=np.array(camera_spec.position_xyz),
                        orientation=orientation,
                        camera_axes=camera_spec.camera_axes,
                    )
                else:
                    camera.set_world_pose(
                        position=np.array(camera_spec.position_xyz),
                        orientation=orientation,
                        camera_axes=camera_spec.camera_axes,
                    )
                cameras[camera_spec.camera_id] = camera

            world.reset()
            for camera in cameras.values():
                camera.initialize()
                camera.set_lens_aperture(0.0)
                camera.set_horizontal_aperture(_CAMERA_HORIZONTAL_APERTURE_M)
                camera.set_focal_length(_CAMERA_FOCAL_LENGTH_M)
                camera.add_distance_to_image_plane_to_frame()
                camera.resume()
            self._step_render_frames(world, _SCENE_WARMUP_STEPS)
        except Exception:
            World.clear_instance()
            raise

        self.world = world
        self.cameras = cameras
        self.robot = robot
        self.table = table
        self.tabletop_object_ids = [spec.object_id for spec in layout]
        self.scene_assets = self._build_scene_assets(self.tabletop_object_ids)

    def capture_camera_payloads(self, session_id: str) -> tuple[list[CameraPayload], list[ArtifactRecord], dict[str, Any]]:
        if not self.cameras or self.world is None or self.session_dir is None:
            return [], [], {"environment_id": self.current_environment_id, "note": "Placeholder camera payload"}

        import numpy as np

        self._step_render_frames(self.world, _SCENE_WARMUP_STEPS)
        camera_specs_by_id = {camera_spec.camera_id: camera_spec for camera_spec in self._camera_mount_specs()}

        payloads: list[CameraPayload] = []
        artifact_records: list[ArtifactRecord] = []
        for camera_id, camera in self.cameras.items():
            rgba = np.asarray(camera.get_rgba(), dtype=np.uint8)
            current_frame = camera.get_current_frame(clone=True)
            depth = current_frame.get("distance_to_image_plane")
            if depth is None:
                raise RuntimeError(
                    f"Camera {camera_id} depth annotator did not return distance_to_image_plane data."
                )
            depth_image = np.asarray(depth, dtype=np.float32)

            rgb_artifact = self._write_rgb_artifact(session_id, camera_id, rgba)
            depth_artifact = self._write_depth_artifact(session_id, camera_id, depth_image)

            intrinsics_matrix = np.asarray(camera.get_intrinsics_matrix(), dtype=float)
            camera_position, camera_orientation_wxyz = camera.get_world_pose(camera_axes="world")
            width, height = camera.get_resolution()
            camera_spec = camera_specs_by_id[camera_id]
            payloads.append(
                CameraPayload(
                    camera_id=camera_id,
                    rgb_image=ArtifactRef(
                        artifact_id=rgb_artifact.artifact_id,
                        content_type=rgb_artifact.content_type,
                    ),
                    depth_image=ArtifactRef(
                        artifact_id=depth_artifact.artifact_id,
                        content_type=depth_artifact.content_type,
                    ),
                    intrinsics=CameraIntrinsics(
                        fx=float(intrinsics_matrix[0, 0]),
                        fy=float(intrinsics_matrix[1, 1]),
                        cx=float(intrinsics_matrix[0, 2]),
                        cy=float(intrinsics_matrix[1, 2]),
                        width=int(width),
                        height=int(height),
                    ),
                    extrinsics=CameraExtrinsics(
                        translation=[float(value) for value in camera_position.tolist()],
                        quaternion_wxyz=[
                            float(value) for value in camera_orientation_wxyz.tolist()
                        ],
                    ),
                    ext={
                        "camera_prim_path": camera_spec.prim_path,
                        "depth_unit": "meter",
                        "depth_encoding": "npy-float32",
                        "view_mode": camera_spec.mode,
                    },
                )
            )
            artifact_records.extend([rgb_artifact, depth_artifact])
        return payloads, artifact_records, {"environment_id": self.current_environment_id}

    @staticmethod
    def _step_render_frames(world: object, num_frames: int) -> None:
        for _ in range(num_frames):
            world.step(render=True)

    def _write_rgb_artifact(self, session_id: str, camera_id: str, rgba_image) -> ArtifactRecord:
        from PIL import Image

        artifact_id = new_artifact_id("rgb", session_id)
        artifact_path = get_artifact_path(self.session_dir, artifact_id, ".png")
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        rgb_image = rgba_image[:, :, :3] if rgba_image.shape[-1] == 4 else rgba_image
        Image.fromarray(rgb_image, mode="RGB").save(artifact_path)
        return ArtifactRecord(
            artifact_id=artifact_id,
            session_id=session_id,
            content_type="image/png",
            file_path=str(artifact_path),
            ext={"camera_id": camera_id},
        )

    def _write_depth_artifact(self, session_id: str, camera_id: str, depth_image) -> ArtifactRecord:
        import numpy as np

        artifact_id = new_artifact_id("depth", session_id)
        artifact_path = get_artifact_path(self.session_dir, artifact_id, ".npy")
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(artifact_path, depth_image.astype(np.float32, copy=False))
        return ArtifactRecord(
            artifact_id=artifact_id,
            session_id=session_id,
            content_type="application/x-npy",
            file_path=str(artifact_path),
            ext={"camera_id": camera_id},
        )

    @staticmethod
    def _build_scene_assets(tabletop_object_ids: list[str]) -> list[str]:
        return [
            "ground",
            "light",
            "table",
            "franka",
            "table_top_camera",
            "table_overview_camera",
            *tabletop_object_ids,
        ]

    @staticmethod
    def _camera_mount_specs() -> tuple[CameraMountSpec, ...]:
        return (
            CameraMountSpec(
                camera_id=_TOP_CAMERA_ID,
                prim_path=_TOP_CAMERA_PRIM_PATH,
                position_xyz=(0.0, 0.0, _TOP_CAMERA_HEIGHT_M),
                mode="top_down",
                euler_xyz_deg=(0.0, 90.0, 0.0),
                camera_axes="world",
            ),
            CameraMountSpec(
                camera_id=_OVERVIEW_CAMERA_ID,
                prim_path=_OVERVIEW_CAMERA_PRIM_PATH,
                position_xyz=_OVERVIEW_CAMERA_POSITION_XYZ,
                mode="robot_opposite_overview",
                euler_xyz_deg=_OVERVIEW_CAMERA_EULER_XYZ_DEG,
                # Match the USD camera prim Euler values shown in the Isaac Sim Property panel.
                euler_extrinsic=False,
                camera_axes="usd",
                use_local_pose=True,
            ),
        )

    @property
    def robot_status(self) -> str:
        return "ready"

    @property
    def action_apis(self) -> list[str]:
        return ["robot.pick_and_place(pick_position, place_position, rotation=None)"]
