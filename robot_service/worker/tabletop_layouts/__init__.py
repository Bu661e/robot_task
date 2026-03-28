from __future__ import annotations

import random

from robot_service.worker.tabletop_layouts.models import TabletopLayoutContext, TabletopObjectSpec


def load_tabletop_layout(environment_id: str, *, rng: random.Random, context: TabletopLayoutContext) -> list[TabletopObjectSpec]:
    from robot_service.worker.tabletop_layouts.default import build_default_layout

    loaders = {
        "env-default": build_default_layout,
    }
    try:
        loader = loaders[environment_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported environment_id: {environment_id}") from exc
    return loader(rng=rng, context=context)
