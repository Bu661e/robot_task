from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from api.schemas import PerceptionRequest
from api.services.artifact_store import ArtifactStore
from api.services.inference_service import PerceptionInferenceService


class StaticBackend:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def invoke_json(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(payload)
        return self.response


def _encode_png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _encode_npy(array: np.ndarray) -> bytes:
    buffer = BytesIO()
    np.save(buffer, array)
    return buffer.getvalue()


def _encode_mask_png_base64(mask_array: np.ndarray) -> str:
    image = Image.fromarray((mask_array > 0).astype(np.uint8) * 255, mode="L")
    return base64.b64encode(_encode_png(image)).decode("ascii")


def _build_request(*, rgb_artifact_id: str, depth_artifact_id: str) -> PerceptionRequest:
    return PerceptionRequest.model_validate(
        {
            "task": {
                "task_id": "1",
                "instruction": "Pick up the bottle.",
                "object_texts": ["bottle"],
            },
            "observations": [
                {
                    "camera_id": "table_top",
                    "rgb_image": {"artifact_id": rgb_artifact_id},
                    "depth_image": {"artifact_id": depth_artifact_id},
                    "intrinsics": {
                        "fx": 100.0,
                        "fy": 100.0,
                        "cx": 2.0,
                        "cy": 2.0,
                        "width": 4,
                        "height": 4,
                    },
                    "timestamp": "2026-03-28T02:40:12Z",
                    "ext": {
                        "depth_unit": "meter",
                        "depth_encoding": "npy-float32",
                    },
                }
            ],
            "context": {
                "session_id": "sess_1",
                "environment_id": "env-default",
            },
            "options": {
                "include_mask_artifacts": True,
                "include_visualization_artifacts": False,
                "include_debug_artifacts": True,
                "include_mesh_glb_artifacts": False,
                "include_gaussian_ply_artifacts": False,
                "include_pointcloud_artifacts": False,
                "max_objects_per_label": 2,
            },
            "ext": {},
        }
    )


def _build_store(tmp_path: Path) -> tuple[ArtifactStore, str, str]:
    artifact_store = ArtifactStore(tmp_path / "artifacts")
    rgb_image = Image.new("RGB", (4, 4), color=(32, 64, 96))
    rgb_metadata = artifact_store.save_bytes(
        artifact_type="rgb_image",
        filename="rgb.png",
        content_type="image/png",
        data=_encode_png(rgb_image),
    )
    depth_metadata = artifact_store.save_bytes(
        artifact_type="depth_image",
        filename="depth.npy",
        content_type="application/x-npy",
        data=_encode_npy(np.ones((4, 4), dtype=np.float32)),
    )
    return artifact_store, rgb_metadata.artifact_id, depth_metadata.artifact_id


def test_infer_saves_mask_artifact_and_exposes_partial_sam3_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_store, rgb_artifact_id, depth_artifact_id = _build_store(tmp_path)
    service = PerceptionInferenceService(artifact_store)
    service.sam3_backend = StaticBackend(
        {
            "status": "ok",
            "response": {
                "backend": "sam3",
                "status": "ok",
                "detections": [
                    {
                        "label": "bottle",
                        "source_object_text": "bottle",
                        "score": 0.95,
                        "bbox_2d_xyxy": [0, 0, 3, 3],
                        "mask_png_base64": _encode_mask_png_base64(
                            np.array(
                                [
                                    [1, 1, 0, 0],
                                    [1, 1, 0, 0],
                                    [0, 0, 0, 0],
                                    [0, 0, 0, 0],
                                ],
                                dtype=np.uint8,
                            )
                        ),
                        "ext": {},
                    }
                ],
                "ext": {"model_path": "/root/sam3.pt"},
            },
        }
    )

    def fake_collect_backend_status(*, request_id: str) -> dict[str, object]:
        assert request_id.startswith("perc_req_")
        return {
            "sam3": {"status": "ok", "response": {"backend": "sam3", "status": "ready"}},
            "sam3d_objects": {
                "status": "ok",
                "response": {"backend": "sam3d_objects", "status": "not_implemented"},
            },
        }

    monkeypatch.setattr(service, "_collect_backend_status", fake_collect_backend_status)

    response = service.infer(
        _build_request(
            rgb_artifact_id=rgb_artifact_id,
            depth_artifact_id=depth_artifact_id,
        )
    )

    assert response.success is False
    assert response.error == {
        "code": "NOT_IMPLEMENTED",
        "message": "SAM3 produced 2D candidate masks for one or more observations, but 3D reconstruction is not integrated yet.",
    }
    assert response.ext["matched_object_texts"] == ["bottle"]
    assert response.ext["unmatched_object_texts"] == []

    observation_result = response.observation_results[0]
    assert observation_result.success is False
    assert observation_result.ext["sam3_candidate_count"] == 1
    assert observation_result.ext["sam3_matched_object_texts"] == ["bottle"]
    assert len(observation_result.scene_artifacts.debug_artifact_ids) == 1

    detection_summary = observation_result.ext["sam3_detections"][0]
    mask_artifact_id = detection_summary["source_mask_artifact_id"]
    assert isinstance(mask_artifact_id, str)
    mask_metadata = artifact_store.get_metadata(mask_artifact_id)
    assert mask_metadata.artifact_type == "mask_image"
    assert mask_metadata.content_type == "image/png"

    assert service.sam3_backend.calls
    assert service.sam3_backend.calls[0]["mode"] == "infer"


def test_infer_preserves_failure_semantics_when_sam3_bridge_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_store, rgb_artifact_id, depth_artifact_id = _build_store(tmp_path)
    service = PerceptionInferenceService(artifact_store)
    service.sam3_backend = StaticBackend(
        {
            "status": "failed",
            "stderr": "sam3 crashed",
        }
    )

    def fake_collect_backend_status(*, request_id: str) -> dict[str, object]:
        assert request_id.startswith("perc_req_")
        return {
            "sam3": {"status": "failed"},
            "sam3d_objects": {"status": "ok"},
        }

    monkeypatch.setattr(service, "_collect_backend_status", fake_collect_backend_status)

    response = service.infer(
        _build_request(
            rgb_artifact_id=rgb_artifact_id,
            depth_artifact_id=depth_artifact_id,
        )
    )

    assert response.success is False
    assert response.error == {
        "code": "INTERNAL_ERROR",
        "message": "Inference backends are not producing detections yet. Request validation and internal pointmap generation completed for all observations.",
    }
    assert response.ext["matched_object_texts"] == []
    assert response.ext["unmatched_object_texts"] == ["bottle"]

    observation_result = response.observation_results[0]
    assert observation_result.ext["sam3_candidate_count"] == 0
    assert observation_result.ext["sam3_backend_status"] == "transport_error"
    assert observation_result.error == {
        "code": "INTERNAL_ERROR",
        "message": "SAM3 bridge process did not return a usable JSON payload.",
    }
