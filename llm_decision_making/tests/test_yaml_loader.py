from __future__ import annotations

from pathlib import Path

import pytest

from utils.yaml_loader import load_yaml_file


def test_load_yaml_file_returns_parsed_yaml_data(tmp_path: Path) -> None:
    yaml_file = tmp_path / "prompt.yaml"
    yaml_file.write_text(
        '\n'.join(
            [
                'model: "qwen"',
                "temperature: 0.2",
                "messages:",
                '  - role: "system"',
                '    content: "You are a planner."',
            ]
        ),
        encoding="utf-8",
    )

    yaml_data = load_yaml_file(yaml_file)

    assert yaml_data == {
        "model": "qwen",
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": "You are a planner.",
            }
        ],
    }


def test_load_yaml_file_raises_for_missing_file(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing.yaml"

    with pytest.raises(FileNotFoundError, match="YAML file not found"):
        load_yaml_file(missing_file)


def test_load_yaml_file_raises_for_invalid_yaml(tmp_path: Path) -> None:
    yaml_file = tmp_path / "broken.yaml"
    yaml_file.write_text("messages: [", encoding="utf-8")

    with pytest.raises(ValueError, match="Failed to parse YAML file"):
        load_yaml_file(yaml_file)
