from __future__ import annotations

import base64
import importlib.util
import json
import sys
from io import BytesIO
from pathlib import Path
from typing import Any


MODEL_PATH = Path(__file__).resolve().parent / "sam3.pt"


def _probe_environment() -> dict[str, Any]:
    ultralytics_error: str | None = None
    predictor_available = False
    ultralytics_available = importlib.util.find_spec("ultralytics") is not None
    if ultralytics_available:
        try:
            from ultralytics.models.sam import SAM3SemanticPredictor

            del SAM3SemanticPredictor
            predictor_available = True
        except Exception as exc:  # pragma: no cover - depends on model env
            ultralytics_error = str(exc)

    return {
        "model_path": str(MODEL_PATH),
        "model_exists": MODEL_PATH.is_file(),
        "ultralytics_available": ultralytics_available,
        "predictor_available": predictor_available,
        "ultralytics_error": ultralytics_error,
    }


def _to_numpy(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        return value.numpy()
    return value


def _encode_mask_png(mask: Any) -> str:
    import numpy as np
    from PIL import Image

    mask_array = np.asarray(mask)
    if mask_array.ndim != 2:
        raise ValueError("Mask must be a 2D array.")
    mask_uint8 = (mask_array > 0).astype("uint8") * 255
    image = Image.fromarray(mask_uint8, mode="L")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _mask_bbox_xyxy(mask: Any) -> list[int] | None:
    import numpy as np

    mask_array = np.asarray(mask)
    positions = np.argwhere(mask_array > 0)
    if positions.size == 0:
        return None
    y_min, x_min = positions.min(axis=0)
    y_max, x_max = positions.max(axis=0)
    return [int(x_min), int(y_min), int(x_max), int(y_max)]


def _extract_detections(
    result: Any,
    *,
    source_object_text: str,
    max_objects_per_label: int,
) -> list[dict[str, Any]]:
    import numpy as np

    masks = []
    boxes = []
    scores = []

    result_masks = getattr(result, "masks", None)
    if result_masks is not None:
        raw_masks = _to_numpy(getattr(result_masks, "data", None))
        if raw_masks is not None:
            masks = list(np.asarray(raw_masks))

    result_boxes = getattr(result, "boxes", None)
    if result_boxes is not None:
        raw_boxes = _to_numpy(getattr(result_boxes, "xyxy", None))
        if raw_boxes is not None:
            boxes = [list(map(int, box.tolist())) for box in np.asarray(raw_boxes)]

        raw_scores = _to_numpy(getattr(result_boxes, "conf", None))
        if raw_scores is not None:
            scores = [float(score) for score in np.asarray(raw_scores).tolist()]

    num_candidates = min(max_objects_per_label, max(len(masks), len(boxes)))
    detections: list[dict[str, Any]] = []
    for candidate_index in range(num_candidates):
        mask = masks[candidate_index] if candidate_index < len(masks) else None
        bbox = boxes[candidate_index] if candidate_index < len(boxes) else None
        if bbox is None and mask is not None:
            bbox = _mask_bbox_xyxy(mask)
        if bbox is None:
            continue

        detections.append(
            {
                "label": source_object_text,
                "source_object_text": source_object_text,
                "score": scores[candidate_index] if candidate_index < len(scores) else 1.0,
                "bbox_2d_xyxy": bbox,
                "mask_png_base64": _encode_mask_png(mask) if mask is not None else None,
                "ext": {
                    "rank_within_label": candidate_index,
                },
            }
        )
    return detections


def _run_preflight() -> dict[str, Any]:
    probe = _probe_environment()
    return {
        "backend": "sam3",
        "status": "ready"
        if probe["model_exists"] and probe["predictor_available"]
        else "unavailable",
        "detections": [],
        "ext": probe,
    }


def _run_infer(payload: dict[str, Any]) -> dict[str, Any]:
    probe = _probe_environment()
    if not probe["model_exists"] or not probe["predictor_available"]:
        return {
            "backend": "sam3",
            "status": "unavailable",
            "detections": [],
            "error_message": "SAM3 model file or predictor dependency is unavailable.",
            "ext": probe,
        }

    image_path = payload.get("image_path")
    if not isinstance(image_path, str) or not image_path.strip():
        return {
            "backend": "sam3",
            "status": "failed",
            "detections": [],
            "error_message": "image_path is required for infer mode.",
            "ext": probe,
        }

    object_texts = payload.get("object_texts")
    if not isinstance(object_texts, list):
        return {
            "backend": "sam3",
            "status": "failed",
            "detections": [],
            "error_message": "object_texts must be a list of strings.",
            "ext": probe,
        }

    max_objects_per_label = payload.get("max_objects_per_label", 1)
    try:
        max_objects = max(1, int(max_objects_per_label))
    except (TypeError, ValueError):
        max_objects = 1

    try:
        from ultralytics.models.sam import SAM3SemanticPredictor
    except Exception as exc:  # pragma: no cover - depends on model env
        return {
            "backend": "sam3",
            "status": "failed",
            "detections": [],
            "error_message": str(exc),
            "ext": probe,
        }

    overrides = {
        "conf": 0.25,
        "task": "segment",
        "mode": "predict",
        "model": str(MODEL_PATH),
        "save": False,
        "verbose": False,
    }

    try:
        predictor = SAM3SemanticPredictor(overrides=overrides)
        predictor.set_image(image_path)
        detections: list[dict[str, Any]] = []
        for raw_object_text in object_texts:
            if not isinstance(raw_object_text, str):
                continue
            object_text = raw_object_text.strip()
            if not object_text:
                continue

            results = predictor(text=[object_text])
            if not results:
                continue
            result = results[0] if isinstance(results, list) else results
            detections.extend(
                _extract_detections(
                    result,
                    source_object_text=object_text,
                    max_objects_per_label=max_objects,
                )
            )
    except Exception as exc:  # pragma: no cover - depends on model env
        return {
            "backend": "sam3",
            "status": "failed",
            "detections": [],
            "error_message": str(exc),
            "ext": probe,
        }

    return {
        "backend": "sam3",
        "status": "ok",
        "detections": detections,
        "ext": probe,
    }


def main() -> int:
    payload = json.load(sys.stdin)
    mode = payload.get("mode")
    if mode == "preflight":
        response = _run_preflight()
    else:
        response = _run_infer(payload)
    json.dump(response, sys.stdout, ensure_ascii=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
