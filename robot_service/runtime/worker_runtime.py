from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import threading
import time
from typing import Any

from llm_decision_making.modules.schemas import CameraInfo, FramePacket, PointMapPacket
from robot_service.config import FRANKA_PHOTO_POSE_CONFIG, FrankaPhotoPoseConfig, RUNTIME_CONFIG, RuntimeConfig

from robot_service.scenes import (
    BaseEnvironmentBuilder,
    BaseEnvironmentSpec,
    DesktopSceneSpec,
    get_desktop_scene_builder,
)


@dataclass
class CaptureFrameResponse:
    frame_packet: FramePacket
    point_map_packet: PointMapPacket


@dataclass
class PendingCaptureRequest:
    completed_event: threading.Event
    response: CaptureFrameResponse | None = None
    error: Exception | None = None


class RobotWorkerRuntime:
    def __init__(self, scene_id: str, session_dir: Path, headless: bool) -> None:
        self.scene_id = scene_id
        self.session_dir = session_dir
        self.headless = headless
        self.frame_output_dir = session_dir / "robot_frames"
        self.ready = False
        self.base_environment_loaded = False
        self.desktop_scene_loaded = False
        self.last_error: str | None = None
        self._frame_index = 0
        self._simulation_app: Any | None = None
        self._world: Any | None = None
        self._base_environment_spec: BaseEnvironmentSpec | None = None
        self._desktop_scene_spec: DesktopSceneSpec | None = None
        self._shutdown_requested = False
        self._reset_requested = False
        self._pending_capture_request: PendingCaptureRequest | None = None
        self._steps_before_ready = 0
        self._runtime_config: RuntimeConfig = RUNTIME_CONFIG

    def initialize_best_effort(self) -> None:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.frame_output_dir.mkdir(parents=True, exist_ok=True)

        try:
            self._initialize_isaac_runtime()
        except Exception as exc:
            self.ready = False
            self.last_error = str(exc)

    def build_health_payload(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "scene_id": self.scene_id,
            "base_environment_loaded": self.base_environment_loaded,
            "desktop_scene_loaded": self.desktop_scene_loaded,
            "frame_output_dir": str(self.frame_output_dir),
            "error": self.last_error,
        }

    def capture_frame(self) -> tuple[FramePacket, PointMapPacket]:
        self._ensure_ready()
        if self._simulation_app is None or self._world is None:
            raise RuntimeError("Isaac Sim runtime 尚未初始化，无法采帧。")
        if self._pending_capture_request is not None:
            raise RuntimeError("当前已有一个 capture_frame 请求正在执行，请稍后重试。")

        capture_request: PendingCaptureRequest = PendingCaptureRequest(
            completed_event=threading.Event(),
        )
        self._pending_capture_request = capture_request

        finished_in_time = capture_request.completed_event.wait(
            timeout=self._runtime_config.capture_request_timeout_s
        )
        if not finished_in_time:
            if self._pending_capture_request is capture_request:
                self._pending_capture_request = None
            raise TimeoutError("capture_frame 等待主线程采帧超时。")
        if capture_request.error is not None:
            raise capture_request.error
        if capture_request.response is None:
            raise RuntimeError("capture_frame 未返回结果。")

        capture_response: CaptureFrameResponse = capture_request.response
        return capture_response.frame_packet, capture_response.point_map_packet

    def pick_and_place(
        self,
        pick_position: list[float],
        place_position: list[float],
        rotation: list[float] | None,
    ) -> dict[str, object]:
        self._ensure_ready()
        _ = (pick_position, place_position, rotation)
        raise NotImplementedError(
            "pick_and_place 尚未接入 Isaac Sim 5.0.0 的 Franka 控制器。"
            "下个 session 需要把 RobotProxy 的结构化动作映射到仿真侧控制器。"
        )

    def reset(self) -> dict[str, object]:
        self._ensure_ready()
        if self._desktop_scene_spec is not None:
            self.ready = False
            self._steps_before_ready = self._desktop_scene_spec.stabilization_steps
        self._reset_requested = True
        return {
            "success": True,
            "message": "worker 已请求重置当前场景。",
        }

    def shutdown(self) -> dict[str, object]:
        self._shutdown_requested = True
        return {
            "success": True,
            "message": "worker 已收到关闭请求。",
        }

    def run_forever(self) -> None:
        try:
            if self._simulation_app is None:
                self._wait_without_simulation_app()
                return

            while not self._shutdown_requested and self._simulation_app.is_running():
                self._process_pending_actions()
                if self._world is not None:
                    self._world.step(render=True)
                else:
                    self._simulation_app.update()
                self._update_ready_state()
        except Exception as exc:
            self.ready = False
            self.last_error = str(exc)
            self._wait_without_simulation_app()

    def close(self) -> None:
        if self._simulation_app is not None:
            self._simulation_app.close()
            self._simulation_app = None

    def _initialize_isaac_runtime(self) -> None:
        from isaacsim import SimulationApp

        self._simulation_app = SimulationApp({"headless": self.headless})
        from isaacsim.core.api import World

        self._world = World(stage_units_in_meters=1.0)

        base_environment_builder = BaseEnvironmentBuilder()
        self._base_environment_spec = base_environment_builder.build(self._world)
        self.base_environment_loaded = True

        desktop_scene_builder = get_desktop_scene_builder(self.scene_id)
        self._desktop_scene_spec = desktop_scene_builder.build(
            self._world,
            self._base_environment_spec,
        )
        self.desktop_scene_loaded = True

        self._world.reset()
        self._apply_franka_photo_pose_if_configured()
        self._initialize_camera_sensor()
        self.ready = False
        self._steps_before_ready = self._desktop_scene_spec.stabilization_steps
        self.last_error = None

    def _ensure_ready(self) -> None:
        if not self.ready:
            raise RuntimeError(
                "Isaac Sim worker 尚未 ready。请先检查 /health 返回和 worker 日志。"
            )

    def _update_ready_state(self) -> None:
        if self.last_error is not None:
            return
        if not self.base_environment_loaded or not self.desktop_scene_loaded:
            return
        if self.ready:
            return
        if self._steps_before_ready > 0:
            self._steps_before_ready -= 1
            return
        self.ready = True

    def _wait_without_simulation_app(self) -> None:
        while not self._shutdown_requested:
            time.sleep(self._runtime_config.idle_sleep_s)

    def _process_pending_actions(self) -> None:
        if self._reset_requested:
            self._reset_requested = False
            self._reset_world_on_main_thread()
        if self._pending_capture_request is not None:
            self._process_capture_request_on_main_thread()

    def _reset_world_on_main_thread(self) -> None:
        if self._world is None:
            return

        self._world.reset()
        self._apply_franka_photo_pose_if_configured()
        self._initialize_camera_sensor()

    def _process_capture_request_on_main_thread(self) -> None:
        capture_request: PendingCaptureRequest | None = self._pending_capture_request
        self._pending_capture_request = None
        if capture_request is None:
            return

        try:
            capture_request.response = self._capture_frame_on_main_thread()
        except Exception as exc:
            capture_request.error = exc
        finally:
            capture_request.completed_event.set()

    def _apply_franka_photo_pose_if_configured(self) -> None:
        import numpy as np

        if self._world is None:
            return

        photo_pose_config: FrankaPhotoPoseConfig = FRANKA_PHOTO_POSE_CONFIG
        if not photo_pose_config.enabled or not photo_pose_config.apply_on_reset:
            return
        if not self._world.scene.object_exists("franka"):
            return

        joint_positions = np.array(photo_pose_config.joint_positions, dtype=float)
        joint_velocities = np.array(photo_pose_config.joint_velocities, dtype=float)
        if joint_positions.shape != joint_velocities.shape:
            raise ValueError(
                "robot/config.py 中的 FRANKA_PHOTO_POSE_CONFIG 关节位置与速度维度不一致。"
            )

        franka_robot: Any = self._world.scene.get_object("franka")
        franka_robot.set_joint_positions(joint_positions)
        franka_robot.set_joint_velocities(joint_velocities)

    def _initialize_camera_sensor(self) -> None:
        camera_sensor: Any = self._get_camera_sensor()
        if camera_sensor.get_render_product_path() is None:
            camera_sensor.initialize()
        current_frame: dict[str, Any] = camera_sensor.get_current_frame()
        if "distance_to_image_plane" not in current_frame:
            camera_sensor.add_distance_to_image_plane_to_frame()
        if camera_sensor.is_paused():
            camera_sensor.resume()

    def _capture_frame_on_main_thread(self) -> CaptureFrameResponse:
        import numpy as np
        from PIL import Image

        if self._world is None:
            raise RuntimeError("World 尚未初始化，无法采帧。")

        camera_sensor: Any = self._get_camera_sensor()
        rgba_array, depth_array = self._wait_for_camera_arrays(camera_sensor=camera_sensor)
        if rgba_array.ndim != 3 or rgba_array.shape[2] < 3:
            raise ValueError(f"顶视相机 RGB 数据形状异常: {rgba_array.shape}")
        if depth_array.ndim == 3 and depth_array.shape[2] == 1:
            depth_array = depth_array[:, :, 0]
        if depth_array.ndim != 2:
            raise ValueError(f"顶视相机深度数据形状异常: {depth_array.shape}")

        depth_array = np.asarray(depth_array, dtype=np.float32)
        point_map_depth_array = depth_array.copy()
        point_map_depth_array[~np.isfinite(point_map_depth_array)] = 0.0

        height_px: int = int(depth_array.shape[0])
        width_px: int = int(depth_array.shape[1])
        image_points_2d = _build_image_points_grid(width_px=width_px, height_px=height_px)
        camera_points_flat = camera_sensor.get_camera_points_from_image_coords(
            image_points_2d,
            point_map_depth_array.reshape(-1),
            device="cpu",
        )
        camera_points_array = np.asarray(camera_points_flat, dtype=np.float32)
        point_map_array = camera_points_array.reshape(height_px, width_px, 3)

        frame_id = f"frame_{self._frame_index:04d}"
        timestamp = datetime.now(timezone.utc).isoformat()
        rgb_path = self.frame_output_dir / f"{frame_id}_rgb.png"
        depth_path = self.frame_output_dir / f"{frame_id}_depth.npy"
        point_map_path = self.frame_output_dir / f"{frame_id}_point_map.npy"

        rgb_uint8_array = _to_uint8_rgba_array(rgba_array=rgba_array)
        Image.fromarray(rgb_uint8_array[:, :, :3], mode="RGB").save(rgb_path)
        np.save(depth_path, depth_array.astype(np.float32, copy=False))
        np.save(point_map_path, point_map_array.astype(np.float32, copy=False))

        intrinsic_matrix = np.asarray(camera_sensor.get_intrinsics_matrix(device="cpu"), dtype=np.float32)
        world_to_camera_matrix = np.asarray(camera_sensor.get_view_matrix_ros(device="cpu"), dtype=np.float32)
        camera_to_world_matrix = np.linalg.inv(world_to_camera_matrix)

        camera_info: CameraInfo = {
            "intrinsic": _matrix3x3_to_list(intrinsic_matrix),
            "extrinsics_camera_to_world": _matrix4x4_to_list(camera_to_world_matrix),
        }
        frame_packet: FramePacket = {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "coordinate_frame": "camera",
            "rgb_path": str(rgb_path),
            "depth_path": str(depth_path),
            "camera": camera_info,
        }
        point_map_packet: PointMapPacket = {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "coordinate_frame": "camera",
            "point_map_path": str(point_map_path),
            "point_format": "xyz_camera",
        }
        self._frame_index += 1
        capture_response: CaptureFrameResponse = CaptureFrameResponse(
            frame_packet=frame_packet,
            point_map_packet=point_map_packet,
        )
        return capture_response

    def _wait_for_camera_arrays(self, camera_sensor: Any) -> tuple[Any, Any]:
        import numpy as np

        if self._world is None:
            raise RuntimeError("World 尚未初始化，无法等待相机数据。")

        minimum_render_steps: int = max(1, self._runtime_config.capture_render_steps)
        max_render_steps: int = max(
            minimum_render_steps,
            self._runtime_config.capture_max_wait_render_steps,
        )
        last_rgba_shape: tuple[int, ...] = tuple()
        last_depth_shape: tuple[int, ...] = tuple()

        for render_step_index in range(1, max_render_steps + 1):
            self._world.step(render=True)

            rgba_image = camera_sensor.get_rgba(device="cpu")
            depth_image = camera_sensor.get_depth(device="cpu")
            rgba_array = np.asarray(rgba_image) if rgba_image is not None else np.array([])
            depth_array = np.asarray(depth_image) if depth_image is not None else np.array([])
            last_rgba_shape = tuple(int(value) for value in rgba_array.shape)
            last_depth_shape = tuple(int(value) for value in depth_array.shape)

            if render_step_index < minimum_render_steps:
                continue
            if rgba_array.size == 0 or depth_array.size == 0:
                continue
            return rgba_array, depth_array

        raise RuntimeError(
            "顶视相机在等待渲染后仍未返回有效 RGB/Depth 数据。"
            f"render_steps={max_render_steps}, "
            f"rgb_shape={last_rgba_shape}, depth_shape={last_depth_shape}"
        )

    def _get_camera_sensor(self) -> Any:
        if self._world is None:
            raise RuntimeError("World 尚未初始化，无法获取相机对象。")
        if self._base_environment_spec is None:
            raise RuntimeError("基础环境尚未初始化，无法获取相机对象。")
        if not self._world.scene.object_exists(self._base_environment_spec.camera_name):
            raise RuntimeError(
                "当前 scene 中未找到顶视相机对象: "
                f"{self._base_environment_spec.camera_name}"
            )
        return self._world.scene.get_object(self._base_environment_spec.camera_name)


def _build_image_points_grid(width_px: int, height_px: int) -> Any:
    import numpy as np

    x_coordinates = np.linspace(0.5, width_px - 0.5, width_px, dtype=np.float32)
    y_coordinates = np.linspace(0.5, height_px - 0.5, height_px, dtype=np.float32)
    grid_x, grid_y = np.meshgrid(x_coordinates, y_coordinates, indexing="xy")
    return np.column_stack((grid_x.reshape(-1), grid_y.reshape(-1)))


def _to_uint8_rgba_array(rgba_array: Any) -> Any:
    import numpy as np

    rgba_numpy_array = np.asarray(rgba_array)
    if rgba_numpy_array.dtype == np.uint8:
        return rgba_numpy_array

    if np.issubdtype(rgba_numpy_array.dtype, np.floating):
        max_value = float(np.nanmax(rgba_numpy_array)) if rgba_numpy_array.size > 0 else 0.0
        if max_value <= 1.0:
            rgba_numpy_array = rgba_numpy_array * 255.0
    rgba_numpy_array = np.clip(rgba_numpy_array, 0.0, 255.0)
    return rgba_numpy_array.astype(np.uint8)


def _matrix3x3_to_list(matrix: Any) -> list[list[float]]:
    return [
        [float(matrix[0, 0]), float(matrix[0, 1]), float(matrix[0, 2])],
        [float(matrix[1, 0]), float(matrix[1, 1]), float(matrix[1, 2])],
        [float(matrix[2, 0]), float(matrix[2, 1]), float(matrix[2, 2])],
    ]


def _matrix4x4_to_list(matrix: Any) -> list[list[float]]:
    return [
        [float(matrix[0, 0]), float(matrix[0, 1]), float(matrix[0, 2]), float(matrix[0, 3])],
        [float(matrix[1, 0]), float(matrix[1, 1]), float(matrix[1, 2]), float(matrix[1, 3])],
        [float(matrix[2, 0]), float(matrix[2, 1]), float(matrix[2, 2]), float(matrix[2, 3])],
        [float(matrix[3, 0]), float(matrix[3, 1]), float(matrix[3, 2]), float(matrix[3, 3])],
    ]
