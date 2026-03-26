from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

import yaml

YamlScalar: TypeAlias = str | int | float | bool | None
YamlValue: TypeAlias = YamlScalar | list["YamlValue"] | dict[str, "YamlValue"]


def load_yaml_file(yaml_file: Path) -> YamlValue:
    if not yaml_file.is_file():
        raise FileNotFoundError(f"YAML file not found: {yaml_file}")

    try:
        with yaml_file.open("r", encoding="utf-8") as file_obj:
            yaml_data = yaml.safe_load(file_obj)
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse YAML file: {yaml_file}") from exc

    return yaml_data
