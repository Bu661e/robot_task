from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


def _as_mapping(payload: object) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("Expected mapping payload.")

    return payload


def _as_mapping_list(payload: Mapping[str, object], key: str) -> list[Mapping[str, object]]:
    raw_value = payload[key]
    if not isinstance(raw_value, list):
        raise ValueError(f"Expected list field: {key}")

    return [_as_mapping(item) for item in raw_value]


def _as_str(payload: Mapping[str, object], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise ValueError(f"Expected string field: {key}")

    return value


def _as_optional_str(payload: Mapping[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Expected optional string field: {key}")

    return value


def _as_bool(payload: Mapping[str, object], key: str) -> bool:
    value = payload[key]
    if not isinstance(value, bool):
        raise ValueError(f"Expected boolean field: {key}")

    return value


def _as_float(payload: Mapping[str, object], key: str) -> float:
    value = payload[key]
    if not isinstance(value, int | float):
        raise ValueError(f"Expected numeric field: {key}")

    return float(value)


def _as_int(payload: Mapping[str, object], key: str) -> int:
    value = payload[key]
    if not isinstance(value, int):
        raise ValueError(f"Expected integer field: {key}")

    return value


def _as_dict(payload: Mapping[str, object], key: str) -> dict[str, object]:
    raw_value = payload.get(key, {})
    if not isinstance(raw_value, Mapping):
        raise ValueError(f"Expected mapping field: {key}")

    return dict(raw_value)


def _as_str_list(payload: Mapping[str, object], key: str) -> list[str]:
    raw_value = payload[key]
    if not isinstance(raw_value, list):
        raise ValueError(f"Expected list field: {key}")
    if not all(isinstance(item, str) for item in raw_value):
        raise ValueError(f"Expected string list field: {key}")

    return list(raw_value)


def _as_int_list(payload: Mapping[str, object], key: str, *, length: int) -> list[int]:
    raw_value = payload[key]
    if not isinstance(raw_value, list):
        raise ValueError(f"Expected list field: {key}")
    if len(raw_value) != length:
        raise ValueError(f"Expected list field with length {length}: {key}")
    if not all(isinstance(item, int) for item in raw_value):
        raise ValueError(f"Expected integer list field: {key}")

    return list(raw_value)


def _as_float_list(payload: Mapping[str, object], key: str, *, length: int) -> list[float]:
    raw_value = payload[key]
    if not isinstance(raw_value, list):
        raise ValueError(f"Expected list field: {key}")
    if len(raw_value) != length:
        raise ValueError(f"Expected list field with length {length}: {key}")
    if not all(isinstance(item, int | float) for item in raw_value):
        raise ValueError(f"Expected numeric list field: {key}")

    return [float(item) for item in raw_value]


@dataclass(slots=True)
class ArtifactRef:
    artifact_id: str
    content_type: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"artifact_id": self.artifact_id}
        if self.content_type is not None:
            payload["content_type"] = self.content_type
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> ArtifactRef:
        return cls(
            artifact_id=_as_str(payload, "artifact_id"),
            content_type=_as_optional_str(payload, "content_type"),
        )


@dataclass(slots=True)
class Intrinsics:
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int

    def to_dict(self) -> dict[str, object]:
        return {
            "fx": self.fx,
            "fy": self.fy,
            "cx": self.cx,
            "cy": self.cy,
            "width": self.width,
            "height": self.height,
        }


@dataclass(slots=True)
class Extrinsics:
    translation: list[float]
    quaternion_wxyz: list[float]

    def to_dict(self) -> dict[str, object]:
        return {
            "translation": list(self.translation),
            "quaternion_wxyz": list(self.quaternion_wxyz),
        }


@dataclass(slots=True)
class PerceptionObservation:
    camera_id: str
    rgb_image: ArtifactRef
    depth_image: ArtifactRef
    intrinsics: Intrinsics
    extrinsics: Extrinsics | None
    timestamp: str
    ext: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "camera_id": self.camera_id,
            "rgb_image": self.rgb_image.to_dict(),
            "depth_image": self.depth_image.to_dict(),
            "intrinsics": self.intrinsics.to_dict(),
            "timestamp": self.timestamp,
            "ext": dict(self.ext),
        }
        if self.extrinsics is not None:
            payload["extrinsics"] = self.extrinsics.to_dict()
        return payload


@dataclass(slots=True)
class PerceptionTask:
    task_id: str
    instruction: str
    object_texts: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "instruction": self.instruction,
            "object_texts": list(self.object_texts),
        }


@dataclass(slots=True)
class PerceptionContext:
    session_id: str | None = None
    environment_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "environment_id": self.environment_id,
        }


@dataclass(slots=True)
class PerceptionOptions:
    include_mask_artifacts: bool
    include_visualization_artifacts: bool
    include_debug_artifacts: bool
    include_mesh_glb_artifacts: bool
    include_gaussian_ply_artifacts: bool
    include_pointcloud_artifacts: bool
    max_objects_per_label: int

    def to_dict(self) -> dict[str, object]:
        return {
            "include_mask_artifacts": self.include_mask_artifacts,
            "include_visualization_artifacts": self.include_visualization_artifacts,
            "include_debug_artifacts": self.include_debug_artifacts,
            "include_mesh_glb_artifacts": self.include_mesh_glb_artifacts,
            "include_gaussian_ply_artifacts": self.include_gaussian_ply_artifacts,
            "include_pointcloud_artifacts": self.include_pointcloud_artifacts,
            "max_objects_per_label": self.max_objects_per_label,
        }


@dataclass(slots=True)
class PerceptionRequest:
    task: PerceptionTask
    observations: list[PerceptionObservation]
    context: PerceptionContext
    options: PerceptionOptions
    ext: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "task": self.task.to_dict(),
            "observations": [observation.to_dict() for observation in self.observations],
            "context": self.context.to_dict(),
            "options": self.options.to_dict(),
            "ext": dict(self.ext),
        }


@dataclass(slots=True)
class ArtifactMetadata:
    artifact_id: str
    artifact_type: str
    content_type: str
    filename: str
    size_bytes: int
    sha256: str
    created_at: str
    ext: dict[str, object]

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> ArtifactMetadata:
        return cls(
            artifact_id=_as_str(payload, "artifact_id"),
            artifact_type=_as_str(payload, "artifact_type"),
            content_type=_as_str(payload, "content_type"),
            filename=_as_str(payload, "filename"),
            size_bytes=_as_int(payload, "size_bytes"),
            sha256=_as_str(payload, "sha256"),
            created_at=_as_str(payload, "created_at"),
            ext=_as_dict(payload, "ext"),
        )


@dataclass(slots=True)
class DetectedObject:
    instance_id: str
    label: str
    source_object_text: str
    score: float
    source_mask_artifact_id: str | None
    bbox_2d_xyxy: list[int]
    translation_m: list[float]
    quaternion_wxyz: list[float]
    scale_m: list[float]
    mesh_glb_artifact_id: str | None
    gaussian_ply_artifact_id: str | None
    pointcloud_artifact_id: str | None
    ext: dict[str, object]

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> DetectedObject:
        return cls(
            instance_id=_as_str(payload, "instance_id"),
            label=_as_str(payload, "label"),
            source_object_text=_as_str(payload, "source_object_text"),
            score=_as_float(payload, "score"),
            source_mask_artifact_id=_as_optional_str(payload, "source_mask_artifact_id"),
            bbox_2d_xyxy=_as_int_list(payload, "bbox_2d_xyxy", length=4),
            translation_m=_as_float_list(payload, "translation_m", length=3),
            quaternion_wxyz=_as_float_list(payload, "quaternion_wxyz", length=4),
            scale_m=_as_float_list(payload, "scale_m", length=3),
            mesh_glb_artifact_id=_as_optional_str(payload, "mesh_glb_artifact_id"),
            gaussian_ply_artifact_id=_as_optional_str(payload, "gaussian_ply_artifact_id"),
            pointcloud_artifact_id=_as_optional_str(payload, "pointcloud_artifact_id"),
            ext=_as_dict(payload, "ext"),
        )


@dataclass(slots=True)
class SceneArtifacts:
    visualization_artifact_ids: list[str]
    debug_artifact_ids: list[str]

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> SceneArtifacts:
        return cls(
            visualization_artifact_ids=_as_str_list(payload, "visualization_artifact_ids"),
            debug_artifact_ids=_as_str_list(payload, "debug_artifact_ids"),
        )


@dataclass(slots=True)
class ObservationResult:
    camera_id: str
    observation_timestamp: str
    success: bool
    coordinate_frame: str
    detected_objects: list[DetectedObject]
    scene_artifacts: SceneArtifacts
    error: dict[str, object]
    ext: dict[str, object]

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> ObservationResult:
        return cls(
            camera_id=_as_str(payload, "camera_id"),
            observation_timestamp=_as_str(payload, "observation_timestamp"),
            success=_as_bool(payload, "success"),
            coordinate_frame=_as_str(payload, "coordinate_frame"),
            detected_objects=[
                DetectedObject.from_dict(item)
                for item in _as_mapping_list(payload, "detected_objects")
            ],
            scene_artifacts=SceneArtifacts.from_dict(_as_mapping(payload["scene_artifacts"])),
            error=_as_dict(payload, "error"),
            ext=_as_dict(payload, "ext"),
        )


@dataclass(slots=True)
class PerceptionResponse:
    request_id: str
    success: bool
    timestamp: str
    observation_results: list[ObservationResult]
    error: dict[str, object]
    ext: dict[str, object]

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> PerceptionResponse:
        return cls(
            request_id=_as_str(payload, "request_id"),
            success=_as_bool(payload, "success"),
            timestamp=_as_str(payload, "timestamp"),
            observation_results=[
                ObservationResult.from_dict(item)
                for item in _as_mapping_list(payload, "observation_results")
            ],
            error=_as_dict(payload, "error"),
            ext=_as_dict(payload, "ext"),
        )
