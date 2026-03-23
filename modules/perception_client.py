from __future__ import annotations

from .schemas import CameraPerceptionResult, FramePacket, ParsedTask, PointMapPacket


def run_perception(
    parsed_task: ParsedTask,
    frame: FramePacket,
    point_map: PointMapPacket,
) -> CameraPerceptionResult:
    raise NotImplementedError("M4 perception_client is not implemented yet.")
