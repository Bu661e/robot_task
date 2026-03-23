from __future__ import annotations

from .schemas import CameraPerceptionResult, FramePacket, WorldPerceptionResult


def to_world(
    perception: CameraPerceptionResult,
    frame: FramePacket,
) -> WorldPerceptionResult:
    raise NotImplementedError("M5 pose_transformer is not implemented yet.")
