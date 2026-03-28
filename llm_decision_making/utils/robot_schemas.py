from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


def _as_mapping(payload: object) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("Expected mapping payload.")

    return payload


def _as_str(payload: Mapping[str, object], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str):
        raise ValueError(f"Expected string field: {key}")

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


def _as_float_list(payload: Mapping[str, object], key: str) -> list[float]:
    raw_value = payload[key]
    if not isinstance(raw_value, list):
        raise ValueError(f"Expected list field: {key}")

    if not all(isinstance(item, int | float) for item in raw_value):
        raise ValueError(f"Expected numeric list field: {key}")

    return [float(item) for item in raw_value]


def _as_dict(payload: Mapping[str, object], key: str) -> dict[str, object]:
    raw_value = payload.get(key, {})
    if not isinstance(raw_value, Mapping):
        raise ValueError(f"Expected mapping field: {key}")

    return dict(raw_value)


def _as_mapping_list(payload: Mapping[str, object], key: str) -> list[Mapping[str, object]]:
    raw_value = payload[key]
    if not isinstance(raw_value, list):
        raise ValueError(f"Expected list field: {key}")

    return [_as_mapping(item) for item in raw_value]


@dataclass(slots=True)
class ArtifactRef:
    content_type: str
    artifact_id: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> ArtifactRef:
        return cls(
            content_type=_as_str(payload, "content_type"),
            artifact_id=_as_str(payload, "artifact_id"),
        )


@dataclass(slots=True)
class SessionInfo:
    session_id: str
    session_status: str
    backend_type: str
    environment_id: str
    ext: dict[str, object]

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> SessionInfo:
        return cls(
            session_id=_as_str(payload, "session_id"),
            session_status=_as_str(payload, "session_status"),
            backend_type=_as_str(payload, "backend_type"),
            environment_id=_as_str(payload, "environment_id"),
            ext=_as_dict(payload, "ext"),
        )


@dataclass(slots=True)
class CloseSessionResponse:
    session_id: str
    session_status: str
    ext: dict[str, object]

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> CloseSessionResponse:
        return cls(
            session_id=_as_str(payload, "session_id"),
            session_status=_as_str(payload, "session_status"),
            ext=_as_dict(payload, "ext"),
        )


@dataclass(slots=True)
class RobotStatusResponse:
    session_id: str
    timestamp: str
    robot_status: str
    ext: dict[str, object]

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> RobotStatusResponse:
        return cls(
            session_id=_as_str(payload, "session_id"),
            timestamp=_as_str(payload, "timestamp"),
            robot_status=_as_str(payload, "robot_status"),
            ext=_as_dict(payload, "ext"),
        )


@dataclass(slots=True)
class CameraIntrinsics:
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> CameraIntrinsics:
        return cls(
            fx=_as_float(payload, "fx"),
            fy=_as_float(payload, "fy"),
            cx=_as_float(payload, "cx"),
            cy=_as_float(payload, "cy"),
            width=_as_int(payload, "width"),
            height=_as_int(payload, "height"),
        )


@dataclass(slots=True)
class CameraExtrinsics:
    translation: list[float]
    quaternion_xyzw: list[float]

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> CameraExtrinsics:
        return cls(
            translation=_as_float_list(payload, "translation"),
            quaternion_xyzw=_as_float_list(payload, "quaternion_xyzw"),
        )


@dataclass(slots=True)
class CameraExt:
    depth_image: ArtifactRef | None

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> CameraExt:
        depth_image = payload.get("depth_image")
        if depth_image is None:
            return cls(depth_image=None)

        return cls(depth_image=ArtifactRef.from_dict(_as_mapping(depth_image)))


@dataclass(slots=True)
class CameraObservation:
    camera_id: str
    rgb_image: ArtifactRef
    intrinsics: CameraIntrinsics
    extrinsics: CameraExtrinsics
    ext: CameraExt

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> CameraObservation:
        ext_payload = _as_mapping(payload.get("ext", {}))
        if "depth_image" in payload and "depth_image" not in ext_payload:
            ext_payload = dict(ext_payload)
            ext_payload["depth_image"] = payload["depth_image"]

        return cls(
            camera_id=_as_str(payload, "camera_id"),
            rgb_image=ArtifactRef.from_dict(_as_mapping(payload["rgb_image"])),
            intrinsics=CameraIntrinsics.from_dict(_as_mapping(payload["intrinsics"])),
            extrinsics=CameraExtrinsics.from_dict(_as_mapping(payload["extrinsics"])),
            ext=CameraExt.from_dict(ext_payload),
        )


@dataclass(slots=True)
class CameraObservationResponse:
    session_id: str
    timestamp: str
    cameras: list[CameraObservation]
    ext: dict[str, object]

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> CameraObservationResponse:
        return cls(
            session_id=_as_str(payload, "session_id"),
            timestamp=_as_str(payload, "timestamp"),
            cameras=[
                CameraObservation.from_dict(item)
                for item in _as_mapping_list(payload, "cameras")
            ],
            ext=_as_dict(payload, "ext"),
        )
