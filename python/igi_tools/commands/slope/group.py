"""Управление группами откосов: создание, очистка.

Команды:
  IGI_SLOPE_GROUP_CREATE — создать группу из объектов.
  IGI_SLOPE_GROUP_CLEAR  — очистить данные группы с объектов.
"""

from __future__ import annotations

import traceback

from pyrx import Db, Ed, command

from igi_tools.commands.slope.xdata import (
    _ensure_regapp,
    _make_bottom_xdata,
    _make_stroke_xdata,
    _make_top_xdata,
    _new_group_guid,
    _read_xdata,
    _remove_stroke_handles,
    _write_stroke_handles as _xwrite_stroke_handles,
    _xdata_get_str,
    REGAPP_NAME,
    ROLE_BOTTOM,
    ROLE_STROKE,
    ROLE_TOP,
)


# ---------------------------------------------------------------------------
# IGI_SLOPE_GROUP_CREATE
# ---------------------------------------------------------------------------


@command(name="IGI_SLOPE_GROUP_CREATE")
def slope_group_create() -> None:
    """Объединить выбранные объекты в новую группу откоса."""
    try:
        print("\n[IGI Tools] === Создание группы откоса ===")

        db = Db.curDb()

        # 1. Верхний контур
        res, top_oid, _ = Ed.Editor.entSel("\nВыберите верхний контур откоса: ")
        if res != Ed.PromptStatus.eOk:
            return

        # 2. Нижний контур
        res, bot_oid, _ = Ed.Editor.entSel("\nВыберите нижний контур откоса: ")
        if res != Ed.PromptStatus.eOk:
            return

        if top_oid == bot_oid:
            print("\n[IGI Tools] Верхний и нижний контуры — один и тот же объект.")
            return

        # 3. Штрихи (множественный выбор)
        print("\n[IGI Tools] Выберите штрихи откоса (линии):")
        res = Ed.Editor.select()
        if res[0] != Ed.PromptStatus.eOk:
            return
        stroke_ids = res[1].toList()

        # Сортировка штрихов вдоль верхнего контура (индексы — по порядку вдоль контура, а не по выбору)
        try:
            _top_curve_ent = Db.Entity(top_oid, Db.OpenMode.kForRead)
            _top_curve = Db.Curve.cast(_top_curve_ent)
            if _top_curve is not None:
                def _stroke_dist(oid: Db.ObjectId) -> float:
                    try:
                        ent = Db.Entity(oid, Db.OpenMode.kForRead)
                        curve = Db.Curve.cast(ent)
                        if curve is None:
                            ent.close()
                            return 0.0
                        sp = curve.getStartPoint()
                        cp = _top_curve.getClosestPointTo(sp, False)
                        dist = _top_curve.getDistAtPoint(cp)
                        ent.close()
                        return dist
                    except Exception:
                        return 0.0
                stroke_ids.sort(key=_stroke_dist)
            _top_curve_ent.close()
        except Exception:
            pass  # сортировка не удалась — используем порядок выбора

        # 4. Новый GUID
        group_guid = _new_group_guid()
        print(f"\n[IGI Tools] Создание группы: {group_guid[:8]}…")

        _ensure_regapp(db)

        # Подготовка констант для полного xdata
        total_strokes = len(stroke_ids)
        top_handle_str = top_oid.handle().toString()
        bot_handle_str = bot_oid.handle().toString()
        stroke_handles: list[str] = []

        # 5. Назначить полное XData в транзакции
        mgr = db.transactionManager()
        tr = mgr.startTransaction()
        try:
            # Верхний контур
            top_ent = tr.getObject(top_oid, Db.OpenMode.kForWrite)
            top_ent.setXData(
                _make_top_xdata(
                    group_guid, total_strokes, 0.0, 0,
                    0.5, False, 0.0, bot_handle_str,
                )
            )

            # Нижний контур
            bot_ent = tr.getObject(bot_oid, Db.OpenMode.kForWrite)
            bot_ent.setXData(_make_bottom_xdata(group_guid, top_handle_str))

            # Штрихи
            for i, oid in enumerate(stroke_ids):
                ent = tr.getObject(oid, Db.OpenMode.kForWrite)
                ent.setXData(
                    _make_stroke_xdata(
                        group_guid, "", i, False, top_handle_str,
                    )
                )
                stroke_handles.append(oid.handle().toString())

            # Записать хендлы штрихов в расширенный словарь верхнего контура
            _xwrite_stroke_handles(tr, top_oid, stroke_handles)

            mgr.endTransaction()
        except Exception:
            mgr.abortTransaction()
            raise

        print(
            f"[IGI Tools] Группа создана: верхний контур, "
            f"нижний контур, {total_strokes} штрих(ов)."
        )

    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")


# ---------------------------------------------------------------------------
# IGI_SLOPE_GROUP_CLEAR
# ---------------------------------------------------------------------------


@command(name="IGI_SLOPE_GROUP_CLEAR")
def slope_group_clear() -> None:
    """Очистить XData группы откоса с выбранных объектов.

    Если среди выбранных объектов обнаруживается верхний контур откоса,
    у него удаляется Xrecord штрихов из расширенного словаря.
    """
    try:
        print("\n[IGI Tools] === Очистка группы откоса ===")

        db = Db.curDb()

        print("\n[IGI Tools] Выберите объекты для очистки данных группы откоса:")
        res = Ed.Editor.select()
        if res[0] != Ed.PromptStatus.eOk:
            return
        ids = res[1].toList()

        _ensure_regapp(db)

        # Определяем, какие OID — верхние контуры (для чистки словаря)
        top_oids_to_clean: list[Db.ObjectId] = []
        for oid in ids:
            try:
                ent = Db.Entity(oid, Db.OpenMode.kForRead)
                xd = _read_xdata(ent)
                if xd is not None:
                    role = _xdata_get_str(xd, 2)
                    if role == ROLE_TOP:
                        top_oids_to_clean.append(oid)
                ent.close()
            except Exception:
                pass

        # Единая транзакция: чистка xdata + удаление словаря
        mgr = db.transactionManager()
        tr = mgr.startTransaction()
        try:
            for oid in ids:
                try:
                    ent = tr.getObject(oid, Db.OpenMode.kForWrite)
                    ent.setXData([(1001, REGAPP_NAME)])
                except Exception as e:
                    print(f"[IGI Tools] Ошибка очистки xdata: {e}")

            for top_oid in top_oids_to_clean:
                _remove_stroke_handles(tr, top_oid)

            mgr.endTransaction()
        except Exception:
            mgr.abortTransaction()
            raise

        print(f"[IGI Tools] Очищено объектов: {len(ids)}.")

    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")