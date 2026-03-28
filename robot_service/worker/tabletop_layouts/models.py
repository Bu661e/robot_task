from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TabletopLayoutContext:
    table_size_m: float
    table_top_z_m: float


@dataclass(frozen=True)
class TabletopObjectSpec:
    object_id: str
    color_rgb: tuple[float, float, float]
    position_xyz: tuple[float, float, float]
    size_m: float
