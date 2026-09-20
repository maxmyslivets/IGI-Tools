"""Slope hatch configuration persistence."""

from __future__ import annotations

import json
from pathlib import Path

# Default settings
_DEFAULT_LAYER_NAME = "17 Рельеф"
_DEFAULT_STEP = 0.5
_SETTINGS_PATH: Path | None = None

_MODE_NAMES = ("Только длинные", "Чередование")


def _get_settings_path() -> Path:
    global _SETTINGS_PATH
    if _SETTINGS_PATH is None:
        from igi_tools.paths import get_resources_dir

        _SETTINGS_PATH = get_resources_dir() / "slope_hatch_settings.json"
    return _SETTINGS_PATH


def _load_settings() -> dict:
    try:
        with open(_get_settings_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_settings(data: dict) -> None:
    try:
        path = _get_settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # non-critical