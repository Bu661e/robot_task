# S1 perception_service Todo

Module goal:
- Expose one HTTP endpoint for the full perception chain.
- Internally run `SAM3 -> SAM3D` in that fixed order.
- Return object-level mask files and 3D results in camera coordinates.

Checklist:
- [ ] Define the HTTP contract for `POST /perception/infer`.
- [ ] Define request/response validation for `PerceptionRequest` and `PerceptionHTTPResponse`.
- [ ] Decode incoming RGB and point map payloads from base64.
- [ ] Read `object_texts` and run `SAM3` once per label.
- [ ] Preserve the `label -> mask` relationship for every candidate instance.
- [ ] Save or retain SAM3 intermediate results for debugging.
- [ ] If SAM3 produces no mask at all, return `success=false` with `error.code == "SAM3_NO_MASK"` and stop.
- [ ] Pass SAM3 outputs to SAM3D with one-to-one instance correspondence.
- [ ] Build each returned object with `instance_id`, `label`, `source_mask_id`, `mask_file`, and mandatory `3d_info` fields.
- [ ] Ensure every returned object includes `translation_m`, `rotation_wxyz`, and `scale_m`.
- [ ] Include the mask file content directly in the HTTP response.
- [ ] Add tests for no-mask failure, single-label multi-instance output, and multi-label output.
