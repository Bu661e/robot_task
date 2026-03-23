from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any

from modules.schemas import FramePacket, PointMapPacket
from robot.config import FRANKA_PHOTO_POSE_CONFIG, FrankaPhotoPoseConfig, RUNTIME_CONFIG, RuntimeConfig

from robot.scenes import (
    BaseEnvironmentBuilder,
    BaseEnvironmentSpec,
    DesktopSceneSpec,
    get_desktop_scene_builder,
)


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

        frame_id = f"frame_{self._frame_index:04d}"
        timestamp = datetime.now(timezone.utc).isoformat()
        rgb_path = self.frame_output_dir / f"{frame_id}_rgb.png"
        depth_path = self.frame_output_dir / f"{frame_id}_depth.npy"
        point_map_path = self.frame_output_dir / f"{frame_id}_point_map.npy"
        _ = (rgb_path, depth_path, point_map_path, timestamp)

        raise NotImplementedError(
            "capture_frame 尚未接入 Isaac Sim 5.0.0 相机采样逻辑。"
            "下个 session 需要在 robot/runtime/worker_runtime.py 中补齐 RGB、Depth、point map "
            "写盘以及 camera intrinsic / extrinsics 读取。"
        )

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

    def _reset_world_on_main_thread(self) -> None:
        if self._world is None:
            return

        self._world.reset()
        self._apply_franka_photo_pose_if_configured()

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
