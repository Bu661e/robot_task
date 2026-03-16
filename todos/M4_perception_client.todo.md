# M4 perception_client Todo

Module goal:
- Call the remote perception service exactly once per task.
- Package local data into `PerceptionRequest`.
- Save returned mask files locally.
- Build `CameraPerceptionResult` in camera coordinates.

Checklist:
- [ ] Define the local schema for `PerceptionRequest`, `PerceptionHTTPResponse`, and `CameraPerceptionResult`.
- [ ] Load RGB and point map files and encode them as base64 payloads.
- [ ] Build the HTTP request body with `frame_id`, timestamp, coordinate frame, files, and `object_texts`.
- [ ] POST to `/perception/infer` exactly once for each task.
- [ ] Save `perception_request.json` before sending.
- [ ] Save `perception_http_response.json` for both success and failure cases.
- [ ] If `success == false`, stop the pipeline immediately and propagate the remote error.
- [ ] If `success == true`, decode and save each returned mask file to `data/masks/`.
- [ ] Build `masks[]` entries with local `mask_path` values.
- [ ] Build `objects[]` entries while preserving `label`, `source_mask_id`, and fixed `3d_info` fields.
- [ ] Keep `CameraPerceptionResult.coordinate_frame == "camera"`.
- [ ] Save `camera_perception_result.json` only for successful perception runs.
- [ ] Add tests for success, no-mask failure, and malformed response handling.
