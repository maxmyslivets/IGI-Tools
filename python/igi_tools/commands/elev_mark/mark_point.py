"""Команда IGI_ELEV_MARK — отметки «СП_9.2» из ЦМР по кликам."""

from __future__ import annotations

import traceback

from pyrx import Db, Ed, command

from igi_tools.commands.elev_mark.blocks import ensure_block, insert_mark
from igi_tools.commands.elev_mark.dem import ensure_dem_loaded, get_elevation


@command(name="IGI_ELEV_MARK")
def mark_point() -> None:
    """По кликам вставляет блоки «СП_9.2» с отметкой Z из ЦМР."""
    print("\n[IGI Tools] Запуск IGI_ELEV_MARK…")

    try:
        loaded, _ = ensure_dem_loaded()
        if not loaded:
            print("[IGI Tools] ЦМР не загружена. Запустите IGI_DEM_TRACKER для подключения георастра.")
            return

        db = Db.curDb()
        block_id = ensure_block(db)
        if block_id is None:
            return

        print("[IGI Tools] Клик — вставить отметку; Esc — выход; Ctrl+Z — отменить последний блок.")
        while True:
            res, pt = Ed.Editor.getPoint("\nУкажите точку: ")
            if res != Ed.PromptStatus.eOk:
                break
            try:
                elev = get_elevation(pt.x, pt.y)
                if elev is None:
                    print("[IGI Tools] Нет данных ЦМР в этой точке — блок не вставлен.")
                    continue
                if not insert_mark(db, pt.x, pt.y, elev):
                    print("[IGI Tools] Не удалось вставить блок «СП_9.2».")
                    continue
                print(f"[IGI Tools] Отметка Z = {elev:.2f}")
            except Exception:
                traceback.print_exc()
                print("[IGI Tools] Не удалось вставить отметку — продолжаю.")
                continue
    except Exception:
        traceback.print_exc()
