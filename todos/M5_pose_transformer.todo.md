# M5 pose_transformer Todo

Module goal:
- Convert camera-frame perception results into world-frame perception results.
- Use `FramePacket.camera.extrinsics_camera_to_world` as the transform source.

Checklist:
- [ ] Define the `WorldPerceptionResult` output schema.
- [ ] Implement translation transform from camera coordinates to world coordinates.
- [ ] Implement rotation transform from camera-frame quaternion to world-frame quaternion.
- [ ] Keep `scale_m` unchanged during the transform.
- [ ] Preserve metadata such as `instance_id`, `label`, `source_mask_id`, and `3d_info.extra`.
- [ ] Set `coordinate_frame` to `world` in the output.
- [ ] Save `world_perception_result.json` under artifacts.
- [ ] Add a numeric test with a known extrinsic matrix and expected world output.
- [ ] Add a regression test for multiple detected objects in one frame.
