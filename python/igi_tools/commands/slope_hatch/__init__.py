"""Slope hatch: draw hatch lines between two curves (brink and toe)."""

from __future__ import annotations

import math
import traceback

from pyrx import Db, Ge, Ed, command

from igi_tools.commands.slope_hatch.config import (
    _DEFAULT_LAYER_NAME,
    _DEFAULT_STEP,
    _MODE_NAMES,
    _load_settings,
    _save_settings,
)
from igi_tools.commands.slope_hatch.geometry import (
    _find_brink_normal_dir,
    _find_toe_point,
    _redistribute_toe_points,
    _sample_curve,
    _tangent_at,
    _tessellate_curve,
)
from igi_tools.commands.slope_hatch.ui import _show_dialog

# ---------------------------------------------------------------------------
# Layer helper
# ---------------------------------------------------------------------------


def _ensure_layer(db: Db.Database, layer_name: str) -> Db.ObjectId:
    """Create a layer if it doesn't exist. Return its ObjectId."""
    lt = Db.LayerTable(db.layerTableId(), Db.OpenMode.kForRead)
    if lt.has(layer_name):
        oid = lt.getAt(layer_name)
        lt.close()
        return oid
    lt.upgradeOpen()
    rec = Db.LayerTableRecord()
    rec.setName(layer_name)
    rec.setColor(Db.Color(3))  # green
    oid = lt.add(rec)
    lt.close()
    return oid


# ---------------------------------------------------------------------------
# Segment properties
# ---------------------------------------------------------------------------


def _apply_segment_props(line: Db.Line, db: Db.Database) -> None:
    """Apply user-specified properties to the segment."""
    line.setColorIndex(0)                             # ByBlock
    line.setLinetype(db.byLayerLinetype())             # ByLayer
    line.setLinetypeScale(0.5)
    line.setLineWeight(Db.LineWeight.kLnWt015)         # 0.15 mm


# ---------------------------------------------------------------------------
# Main command
# ---------------------------------------------------------------------------


@command(name="IGI_SLOPE_HATCH")
def slope_hatch() -> None:
    """Draw slope hatch lines between brink and toe curves."""
    try:
        print("\n--- Построение штриховки откоса ---")

        saved_state = _load_settings()
        saved_state.setdefault("step", _DEFAULT_STEP)
        saved_state.setdefault("mode_index", 0)
        saved_state.setdefault("layer_mode", 0)
        saved_state.setdefault("custom_layer", _DEFAULT_LAYER_NAME)

        # ── Диалог параметров (с интерактивным выбором слоя) ──
        picked_layer_name: str | None = None

        while True:
            result = _show_dialog(False, False, saved_state)
            if result is None:
                print("\n[IGI Tools] Отменено пользователем.")
                return

            action = result.get("action", "ok")

            if action == "pick_layer":
                res = Ed.Editor.entSel(
                    "\nВыберите объект на целевом слое: "
                )
                if res[0] != Ed.PromptStatus.eOk:
                    print("\n[IGI Tools] Выбор слоя отменён.")
                    continue
                try:
                    ent = Db.Entity(res[1], Db.OpenMode.kForRead)
                    lt = Db.LayerTableRecord(
                        ent.layerId(), Db.OpenMode.kForRead
                    )
                    picked_layer_name = lt.getName()
                    lt.close()
                    ent.close()
                    print(f"\n[IGI Tools] Выбран слой: {picked_layer_name}")
                    saved_state["custom_layer"] = picked_layer_name
                    saved_state["layer_mode"] = 1
                except Exception:
                    print("\n[IGI Tools] Не удалось определить слой.")
                continue

            step = result["step"]
            mode_idx = result["mode_index"]

            layer_mode = result.get("layer_mode", 0)
            if layer_mode == 0:
                layer_name = _DEFAULT_LAYER_NAME
            elif layer_mode == 1:
                layer_name = picked_layer_name or _DEFAULT_LAYER_NAME
            else:
                layer_name = result.get("custom_layer", "") or _DEFAULT_LAYER_NAME

            print(
                f"\n[IGI Tools] Шаг: {step}, режим: {_MODE_NAMES[mode_idx]}, "
                f"слой: {layer_name}"
            )
            break

        # ── Выбрать бровку ──
        res = Ed.Editor.entSel(
            "\nВыберите бровку откоса (Полилиния/Отрезок): "
        )
        if res[0] != Ed.PromptStatus.eOk:
            print("\n[IGI Tools] Выбор бровки отменён.")
            return
        brink_oid = res[1]
        print("\n[IGI Tools] Бровка выбрана.")

        # ── Выбрать подошву ──
        res = Ed.Editor.entSel(
            "\nВыберите подошву откоса (Полилиния/Отрезок): "
        )
        if res[0] != Ed.PromptStatus.eOk:
            print("\n[IGI Tools] Выбор подошвы отменён.")
            return
        toe_oid = res[1]
        print("\n[IGI Tools] Подошва выбрана.")

        # ── Извлечь геометрию ──
        db = Db.curDb()

        ent_brink = Db.Entity(brink_oid, Db.OpenMode.kForRead)
        ent_toe = Db.Entity(toe_oid, Db.OpenMode.kForRead)

        if not ent_brink.isDerivedFrom(Db.Curve.desc()) or not ent_toe.isDerivedFrom(Db.Curve.desc()):
            print("\n[IGI Tools] Оба объекта должны быть кривыми (Полилиния/Отрезок).")
            return

        brink_curve = Db.Curve.cast(ent_brink)
        toe_curve = Db.Curve.cast(ent_toe)
        if brink_curve is None or toe_curve is None:
            print("\n[IGI Tools] Не удалось привести объекты к типу Curve.")
            return

        sample_pts, total_len = _sample_curve(brink_curve, step)
        if len(sample_pts) < 2:
            print("\n[IGI Tools] Бровка слишком коротка.")
            return

        toe_pts = _tessellate_curve(toe_curve, 300)
        if len(toe_pts) < 2:
            print("\n[IGI Tools] Подошва содержит менее 2 точек.")
            return

        layer_id = _ensure_layer(db, layer_name)

        # ── Phase 1: построить все отрезки (бровка → подошва) ──
        raw_pairs: list[tuple[Ge.Point3d, Ge.Point3d]] = []
        prev_toe_pt: Ge.Point3d | None = None

        for i, pt in enumerate(sample_pts):
            tan = _tangent_at(sample_pts, i)
            nrm = _find_brink_normal_dir(pt, toe_curve, tan)

            toe_pt = _find_toe_point(pt, nrm, toe_pts, toe_curve, prev_toe_pt)
            if toe_pt is None:
                continue

            d = math.hypot(pt.x - toe_pt.x, pt.y - toe_pt.y)
            if d < 1e-6:
                continue

            prev_toe_pt = toe_pt
            raw_pairs.append((pt, toe_pt))

        # ── Phase 2: выравнивание точек подошвы ──
        if raw_pairs:
            adjusted = _redistribute_toe_points(raw_pairs, toe_curve, toe_pts)
        else:
            adjusted = []

        # ── Phase 3: создание отрезков в чертеже ──
        count = 0
        for i, (pt, toe_pt) in enumerate(adjusted):
            if mode_idx == 1 and i % 2 == 1:
                end_pt = Ge.Point3d(
                    (pt.x + toe_pt.x) / 2.0,
                    (pt.y + toe_pt.y) / 2.0,
                    0.0,
                )
            else:
                end_pt = toe_pt

            line = Db.Line(pt, end_pt)
            line.setDatabaseDefaults(db)
            line.setLayer(layer_id)
            _apply_segment_props(line, db)
            db.addToModelspace(line)
            count += 1

        ent_brink.close()
        ent_toe.close()

        save_data = {
            "step": step,
            "mode_index": mode_idx,
            "layer_mode": result.get("layer_mode", 0),
            "custom_layer": result.get("custom_layer", _DEFAULT_LAYER_NAME),
        }
        _save_settings(save_data)

        print(f"\n[IGI Tools] Построено отрезков: {count}")

    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")