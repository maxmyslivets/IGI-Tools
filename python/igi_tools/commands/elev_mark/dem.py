"""Доступ к ЦМР, подключённой дем-трекером."""

from __future__ import annotations

import math
import traceback
import numpy as np


def ensure_dem_loaded() -> tuple[bool, object | None]:
    """Проверить, подключена ли ЦМР. Возвращает (загружена, монитор)."""
    from igi_tools.commands import dem_tracker

    mon = dem_tracker.tiff_monitor
    if mon is None:
        return False, None
    return True, mon


def get_elevation(x: float, y: float) -> float | None:
    """Отметка Z из ЦМР в точке (x, y); None, если данных нет или ошибка."""
    try:
        ok, mon = ensure_dem_loaded()
        if not ok:
            return None
        z_raw = next(mon.dataset.sample([(x, y)], masked=True))[0]
        if np.ma.is_masked(z_raw):
            return None
        z = float(z_raw)
        if math.isnan(z) or z < -1000.0 or z > 10000.0:
            return None
        return z
    except Exception:
        traceback.print_exc()
        return None
