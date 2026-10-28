"""Команда IGI_ELEV_MARK_GRID — отметки «СП_9.2» из ЦМР по сетке."""

from __future__ import annotations

import traceback

from pyrx import command


@command(name="IGI_ELEV_MARK_GRID")
def mark_grid() -> None:
    """Отметки «СП_9.2» из ЦМР по сетке (в разработке)."""
    try:
        print("[IGI Tools] IGI_ELEV_MARK_GRID: в разработке.")
    except Exception:
        traceback.print_exc()