# M2 robot_bridge Todo

Module goal:
- Read RGB, depth, and camera parameters from the robot runtime.
- Build a camera-frame `point_map` locally.
- Provide the `robot` control object.
- Support both simulation and real-robot backends with one unified main-process interface.

Checklist:
- [ ] Define the unified `robot_bridge` interface used by the main process.
- [ ] Separate the implementation into a backend-replaceable design:
  - simulation robot backend
  - real robot backend
- [ ] Confirm the Isaac Sim 5.0.0 API path for RGB capture, depth capture, intrinsics, and camera extrinsics for the simulation backend.
- [ ] Define the runtime contract for returning `FramePacket`, `PointMapPacket`, and `robot` together.
- [ ] Generate a unique `frame_id` and timestamp for each sampled frame.
- [ ] Save RGB to `data/frame_XXXX_rgb.png`.
- [ ] Save depth to `data/frame_XXXX_depth.npy`.
- [ ] Build the point map in camera coordinates from depth + intrinsics, avoiding world-frame drift.
- [ ] Save the point map to `data/frame_XXXX_pointmap.npy`.
- [ ] Export `camera.intrinsics` in the required 3x3 format.
- [ ] Export `camera.extrinsics_camera_to_world` in the required 4x4 format.
- [ ] Ensure `FramePacket.coordinate_frame == "camera"`.
- [ ] Ensure `PointMapPacket.coordinate_frame == "camera"` and `point_format == "xyz_camera"`.
- [ ] Wrap or expose only the allowed robot action API: `pick_and_place(pick_position, place_position, rotation=None)`.
- [ ] Ensure the main process does not depend on Isaac Sim-specific objects.
- [ ] Save `frame_packet.json` and `point_map_packet.json` under artifacts.
- [ ] Add a smoke test or mock-based test for one complete frame capture path.
