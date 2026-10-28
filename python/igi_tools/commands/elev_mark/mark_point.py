"""Команда IGI_ELEV_MARK — отметки «СП_9.2» из ЦМР по кликам."""

from __future__ import annotations

import traceback

from pyrx import Db, command
from pyrx.ed.prompt import (
    PromptExceptionCancel,
    PromptExceptionKword,
    PromptExceptionNone,
    get_point,
)

from igi_tools.commands.elev_mark.blocks import (
    ensure_block,
    insert_mark,
    reset_marks_stack,
    undo_last_mark,
)
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

        reset_marks_stack()
        print(
            "[IGI Tools] Клик — вставить отметку; Ctrl+Z или «Отмена» — удалить последнюю; Esc — выход."
        )
        while True:
            try:
                pt = get_point("\nУкажите точку", kwords=(('Отмена', 'Undo'),))
            except PromptExceptionKword:
                if undo_last_mark():
                    print("[IGI Tools] Последняя отметка удалена.")
                else:
                    print("[IGI Tools] Отменять больше нечего.")
                continue
            except PromptExceptionNone:
                break
            except PromptExceptionCancel:
                print("[IGI Tools] Команда завершена.")
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
