"""Команда IGI_ELEV_MARK_LINES — отметки «СП_9.2» из ЦМР вдоль линий."""

from __future__ import annotations

import traceback

from pyrx import command


@command(name="IGI_ELEV_MARK_LINES")
def mark_lines() -> None:
    """Отметки «СП_9.2» из ЦМР вдоль выбранных линий (в разработке)."""
    try:
        print("[IGI Tools] IGI_ELEV_MARK_LINES: в разработке.")
    except Exception:
        traceback.print_exc()