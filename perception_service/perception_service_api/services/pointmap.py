from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from perception_service_api.errors import ApiError
from perception_service_api.schemas import ArtifactMetadata, CameraIntrinsics


@dataclass(slots=True)
class PointmapResult:
    pointmap: np.ndarray
    width: int
    height: int
    valid_fraction: float
    min_depth_m: float | None
    max_depth_m: float | None


def load_rgb_size(metadata: ArtifactMetadata, content_path: Path) -> tuple[int, int]:
    try:
        with Image.open(content_path) as image:
            width, height = image.size
    except Exception as exc:  # pragma: no cover - defensive guard
        raise ApiError(
            status_code=400,
            error_code="UNSUPPORTED_CONTENT_TYPE",
            message="RGB artifact must be a readable image.",
            ext={"details": {"artifact_id": metadata.artifact_id}},
        ) from exc
    return width, height


def load_depth_meters(
    metadata: ArtifactMetadata,
    content_path: Path,
    *,
    depth_scale_m_per_unit: float | None,
) -> np.ndarray:
    filename = metadata.filename.lower()
    content_type = metadata.content_type.lower()

    if filename.endswith(".npy") or content_type == "application/x-npy":
        depth = np.load(content_path, allow_pickle=False)
    elif filename.endswith(".png") or content_type.startswith("image/"):
        with Image.open(content_path) as image:
            depth = np.array(image)
    else:
        raise ApiError(
            status_code=400,
            error_code="UNSUPPORTED_CONTENT_TYPE",
            message="Depth artifact must be PNG or NPY.",
            ext={"details": {"artifact_id": metadata.artifact_id, "content_type": metadata.content_type}},
        )

    if depth.ndim == 3:
        if depth.shape[2] != 1:
            raise ApiError(
                status_code=400,
                error_code="UNSUPPORTED_CONTENT_TYPE",
                message="Depth artifact must be single-channel.",
                ext={"details": {"artifact_id": metadata.artifact_id, "shape": list(depth.shape)}},
            )
        depth = depth[..., 0]

    if depth.ndim != 2:
        raise ApiError(
            status_code=400,
            error_code="UNSUPPORTED_CONTENT_TYPE",
            message="Depth artifact must decode to a 2D array.",
            ext={"details": {"artifact_id": metadata.artifact_id, "shape": list(depth.shape)}},
        )

    if np.issubdtype(depth.dtype, np.integer):
        if depth_scale_m_per_unit is None:
            raise ApiError(
                status_code=400,
                error_code="INVALID_REQUEST",
                message="depth_scale_m_per_unit is required for integer depth images.",
                ext={"details": {"artifact_id": metadata.artifact_id}},
            )
        return depth.astype(np.float32) * float(depth_scale_m_per_unit)

    return depth.astype(np.float32)


def depth_to_pointmap(depth_m: np.ndarray, intrinsics: CameraIntrinsics) -> PointmapResult:
    height, width = depth_m.shape
    if width != intrinsics.width or height != intrinsics.height:
        raise ApiError(
            status_code=400,
            error_code="INVALID_REQUEST",
            message="Depth resolution does not match camera intrinsics.",
            ext={
                "details": {
                    "actual_width": width,
                    "actual_height": height,
                    "expected_width": intrinsics.width,
                    "expected_height": intrinsics.height,
                }
            },
        )

    v_coords, u_coords = np.indices((height, width), dtype=np.float32)
    z = depth_m.astype(np.float32)
    x = ((u_coords - float(intrinsics.cx)) / float(intrinsics.fx)) * z
    y = ((v_coords - float(intrinsics.cy)) / float(intrinsics.fy)) * z

    pointmap = np.stack((x, y, z), axis=-1).astype(np.float32)
    valid_mask = np.isfinite(z) & (z > 0)
    pointmap[~valid_mask] = np.nan

    valid_depths = z[valid_mask]
    min_depth = float(valid_depths.min()) if valid_depths.size else None
    max_depth = float(valid_depths.max()) if valid_depths.size else None
    valid_fraction = float(valid_mask.mean()) if valid_mask.size else 0.0

    return PointmapResult(
        pointmap=pointmap,
        width=width,
        height=height,
        valid_fraction=valid_fraction,
        min_depth_m=min_depth,
        max_depth_m=max_depth,
    )
