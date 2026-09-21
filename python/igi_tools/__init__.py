"""IGI Tools — Python utilities for AutoCAD / Civil 3D via CADPyRx."""

from __future__ import annotations


def _read_version() -> str:
    try:
        from igi_tools.updater import get_installed_version

        return get_installed_version()
    except Exception:
        return "0.0.0"


__version__ = _read_version()
