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

        from igi_tools.updater import get_installed_version, schedule_update_check

        ver = get_installed_version()
        print(
            f"\n[IGI Tools] v{ver} — Python commands loaded "
            "(IGI_DRAW_NOMENCLATURE, IGI_GZU_FROM_GEOJSON, IGI_CHECK_UPDATE)."
        )
        schedule_update_check()
    except Exception:
        traceback.print_exc()
