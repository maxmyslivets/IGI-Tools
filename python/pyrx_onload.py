"""PyRx onload entry — runs after RxLoader starts and finds this file via SupportPath."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def OnPyInitApp() -> None:
    try:
        base = str(BASE_DIR)
        if base not in sys.path:
            sys.path.insert(0, base)
        import igi_tools.commands  # noqa: F401

        print(
            "\n[IGI Tools] Python commands loaded "
            "(IGI_CIRCLES_ON_VERTICES, IGI_DRAW_NOMENCLATURE, IGI_GZU_FROM_GEOJSON)."
        )
    except Exception:
        traceback.print_exc()
