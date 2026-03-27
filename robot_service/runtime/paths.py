from __future__ import annotations

from pathlib import Path


def get_runs_dir(base_dir: Path | str) -> Path:
    return Path(base_dir)


def get_session_run_dir(runs_dir: Path | str, session_id: str) -> Path:
    return Path(runs_dir) / session_id


def get_artifact_path(session_dir: Path | str, artifact_id: str, suffix: str) -> Path:
    normalized_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    return Path(session_dir) / "artifacts" / f"{artifact_id}{normalized_suffix}"

