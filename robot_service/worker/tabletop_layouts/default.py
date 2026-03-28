from __future__ import annotations

import random

from robot_service.worker.tabletop_layouts.models import TabletopLayoutContext, TabletopObjectSpec


_CUBE_SIZE_M = 0.10
_MIN_CENTER_DISTANCE_M = 0.18
_TABLE_MARGIN_M = 0.12
_ROBOT_KEEP_OUT_Y_M = 0.18
_SPAWN_Z_OFFSET_M = 0.02
_MAX_SAMPLING_ATTEMPTS = 200

_RED = (0.85, 0.12, 0.12)
_BLUE = (0.12, 0.24, 0.85)


def build_default_layout(*, rng: random.Random, context: TabletopLayoutContext) -> list[TabletopObjectSpec]:
    half_table = context.table_size_m / 2.0
    xy_limit = half_table - _TABLE_MARGIN_M - (_CUBE_SIZE_M / 2.0)
    x_min = -xy_limit
    x_max = xy_limit
    y_min = -xy_limit + _ROBOT_KEEP_OUT_Y_M
    y_max = xy_limit
    z = context.table_top_z_m + (_CUBE_SIZE_M / 2.0) + _SPAWN_Z_OFFSET_M

    object_defs = [
        ("red_cube_1", _RED),
        ("red_cube_2", _RED),
        ("blue_cube_1", _BLUE),
        ("blue_cube_2", _BLUE),
    ]

    placed_xy: list[tuple[float, float]] = []
    specs: list[TabletopObjectSpec] = []
    for object_id, color_rgb in object_defs:
        x, y = _sample_non_overlapping_xy(rng=rng, x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max, placed_xy=placed_xy)
        placed_xy.append((x, y))
        specs.append(
            TabletopObjectSpec(
                object_id=object_id,
                color_rgb=color_rgb,
                position_xyz=(x, y, z),
                size_m=_CUBE_SIZE_M,
            )
        )
    return specs


def _sample_non_overlapping_xy(
    *,
    rng: random.Random,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    placed_xy: list[tuple[float, float]],
) -> tuple[float, float]:
    for _ in range(_MAX_SAMPLING_ATTEMPTS):
        x = rng.uniform(x_min, x_max)
        y = rng.uniform(y_min, y_max)
        if all(((x - px) ** 2 + (y - py) ** 2) ** 0.5 >= _MIN_CENTER_DISTANCE_M for px, py in placed_xy):
            return x, y
    raise RuntimeError("Failed to sample a non-overlapping default tabletop layout.")
