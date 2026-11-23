"""Slope: draw/edit/delete slope strokes between two curves.

Commands: IGI_SLOPE (create), IGI_SLOPE_EDIT (edit), IGI_SLOPE_DELETE (delete).

Ported from SSTools.Interaction.Slope (VB.NET, CIL-reverse-engineered).
"""

from __future__ import annotations

import math
import traceback

from pyrx import Ap, Db, Ge, Ed, command

from igi_tools.paths import get_template_path
from igi_tools.commands.slope.config import (
    _DEFAULT_BOTTOM_OFFSET,
    _DEFAULT_LAYER,
    _DEFAULT_MID_LENGTH,
    _DEFAULT_MID_RATIO,
    _DEFAULT_SHORT_COUNT,
    _DEFAULT_STEP,
    _DEFAULT_USE_MID_LENGTH,
    _load_settings,
    _save_settings,
)
from igi_tools.commands.slope.geometry import (
    _check_min_strokes,
    _compute_stroke_end,

    _find_best_phase_shift,
    _get_clockwise_order,
    _get_curve_length,
    _is_short_stroke,
    _shift_curve_start,
    _should_reverse_curve,
)
from igi_tools.commands.slope.ui import _show_dialog
from igi_tools.commands.slope.xdata import (
    _clear_xdata,
    _ensure_regapp,
    _make_bottom_xdata,
    _make_stroke_xdata,
    _make_top_xdata,
    _new_group_guid,
    _oid_to_handle_str,
    _read_stroke_handles as _xread_stroke_handles,
    _read_xdata,
    _remove_stroke_handles,
    _try_get_oid_by_handle,
    _write_stroke_handles as _xwrite_stroke_handles,
    _xdata_get_double,
    _xdata_get_int,
    _xdata_get_str,
    ROLE_TOP,
    ROLE_BOTTOM,
    ROLE_STROKE,
)

# ---------------------------------------------------------------------------
# Layer helper
# ---------------------------------------------------------------------------


def _try_import_layer_from_template(
    db: Db.Database, layer_name: str
) -> Db.ObjectId | None:
    """Clone a layer definition from template.dwg into the current drawing."""
    template_path = get_template_path()
    if not template_path.is_file():
        return None

    try:
        src = Db.Database(False, True)
        src.readDwgFile(
            str(template_path),
            Db.DatabaseOpenMode.kForReadAndAllShare,
            False,
            "",
        )
        src.closeInput(True)

        src_lt = Db.LayerTable(src.layerTableId(), Db.OpenMode.kForRead)
        if not src_lt.has(layer_name):
            src_lt.close()
            return None

        src_layer_id = src_lt.getAt(layer_name)
        src_lt.close()

        id_map = Db.IdMapping()
        src.wblockCloneObjects(
            [src_layer_id],
            db.layerTableId(),
            id_map,
            Db.DuplicateRecordCloning.kDrcReplace,
            False,
        )

        lt = Db.LayerTable(db.layerTableId(), Db.OpenMode.kForRead)
        if lt.has(layer_name):
            result = lt.getAt(layer_name)
            lt.close()
            return result
        lt.close()
    except Exception:
        traceback.print_exc()
    return None


def _ensure_layer(db: Db.Database, layer_name: str) -> Db.ObjectId:
    """Create layer if absent, borrowing properties from template.dwg when possible."""
    lt = Db.LayerTable(db.layerTableId(), Db.OpenMode.kForRead)
    if lt.has(layer_name):
        oid = lt.getAt(layer_name)
        lt.close()
        return oid
    lt.close()

    # Try importing from template.dwg first
    imported = _try_import_layer_from_template(db, layer_name)
    if imported is not None:
        return imported

    # Fallback: create with default orange
    lt = Db.LayerTable(db.layerTableId(), Db.OpenMode.kForWrite)
    rec = Db.LayerTableRecord()
    rec.setName(layer_name)
    rec.setColor(Db.Color(165, 82, 0))
    oid = lt.add(rec)
    lt.close()
    return oid


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------


def _select_curve(
    prompt: str,
) -> tuple[Ed.PromptStatus, Db.ObjectId | None, str]:
    """Prompt user to select a Polyline/Curve. Returns (status, oid, err_msg)."""
    res, oid, _ = Ed.Editor.entSel(prompt)
    if res != Ed.PromptStatus.eOk:
        return (res, None, "")
    try:
        ent = Db.Entity(oid, Db.OpenMode.kForRead)
        if not ent.isDerivedFrom(Db.Curve.desc()):
            ent.close()
            return (Ed.PromptStatus.eFailed, None, "Объект не является кривой.")
        ent.close()
        return (Ed.PromptStatus.eOk, oid, "")
    except Exception as e:
        return (Ed.PromptStatus.eFailed, None, str(e))


def _confirm_yes(msg: str) -> bool:
    """Prompt Yes/No with Yes default."""
    try:
        Ed.Editor.initGet(0, "Yes No")
        status, kw = Ed.Editor.getKword(f"\n\r{msg} (Yes/No) <Yes>: ")
        if status == Ed.PromptStatus.eOk and kw == "No":
            return False
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Check curve intersection (stub)
# ---------------------------------------------------------------------------


def _curves_intersect(c1: Db.Curve, c2: Db.Curve) -> bool:
    """Check if two curves intersect. Stub."""
    try:
        coll = Ge.Point3dCollection()
        c1.intersectWith(c2, Db.Intersect.kOnBothOperands, coll)
        return len(coll) > 0
    except Exception:
        return False


def _is_self_intersecting(curve: Db.Curve) -> bool:
    """Stub."""
    return False


def _find_intersection_range(
    f_top: Db.Curve,
    f_bottom: Db.Curve,
) -> tuple[float, float, float, float, bool] | None:
    """Найти точки пересечения и вернуть (top_start, top_end, bot_start, bot_end, need_reverse_bot).

    need_reverse_bot=True когда полезный сегмент нижнего контура проходит
    в обратном направлении относительно его естественного хода (т.е. точки
    пересечения располагаются на нижнем в порядке, обратном верхнему).
    В этом случае caller должен развернуть нижний контур.

    При 2+ точках — диапазон между крайними на обоих контурах.
    При 1 точке — диапазон от начала контура до неё, need_reverse_bot=False.
    None если пересечений нет.
    """
    try:
        coll = f_top.intersectWith(f_bottom, Db.Intersect.kOnBothOperands)
        if not coll or len(coll) < 1:
            return None

        # Собираем ПАРНЫЕ расстояния: (dist_on_top, dist_on_bottom)
        pairs: list[tuple[float, float]] = []
        for p in coll:
            try:
                d_top = f_top.getDistAtPoint(p)
            except Exception:
                try:
                    snap = f_top.getClosestPointTo(p, False)
                    d_top = f_top.getDistAtPoint(snap)
                except Exception:
                    continue
            try:
                d_bot = f_bottom.getDistAtPoint(p)
            except Exception:
                try:
                    snap = f_bottom.getClosestPointTo(p, False)
                    d_bot = f_bottom.getDistAtPoint(snap)
                except Exception:
                    continue
            pairs.append((d_top, d_bot))

        if len(pairs) == 0:
            return None

        if len(pairs) == 1:
            d_top, d_bot = pairs[0]
            return (0.0, d_top, 0.0, d_bot, False)

        # Сортируем по верхнему расстоянию — проверяем соответствие направлений
        pairs.sort(key=lambda x: x[0])
        t_min, b_at_t_min = pairs[0]
        t_max, b_at_t_max = pairs[-1]

        # Если на нижнем дистанции убывают при возрастании верхних,
        # то полезный отрезок на нижнем идёт «задом наперёд» — нужен реверс.
        need_reverse = b_at_t_min > b_at_t_max

        b_start = min(b_at_t_min, b_at_t_max)
        b_end = max(b_at_t_min, b_at_t_max)

        return (t_min, t_max, b_start, b_end, need_reverse)
    except Exception as exc:
        print(f"[IGI Tools] _find_intersection_range: ошибка {exc}")
        return None


# ---------------------------------------------------------------------------
# Helpers that open entity by OID, read, and close
# ---------------------------------------------------------------------------


def _get_curves_from_oids(
    top_oid: Db.ObjectId, bot_oid: Db.ObjectId
) -> tuple[Db.Curve | None, Db.Curve | None]:
    """Open both curves for read, return tuple. Caller must close()."""
    try:
        te = Db.Entity(top_oid, Db.OpenMode.kForRead)
        be = Db.Entity(bot_oid, Db.OpenMode.kForRead)
        tc = Db.Curve.cast(te)
        bc = Db.Curve.cast(be)
        if tc is None or bc is None:
            if tc is None:
                te.close()
            if bc is None:
                be.close()
            return (None, None)
        return (tc, bc)
    except Exception:
        return (None, None)


def _close_curves(tc: Db.Curve | None, bc: Db.Curve | None) -> None:
    """Close both curves if not None."""
    if tc is not None:
        tc.close()
    if bc is not None:
        bc.close()


# ---------------------------------------------------------------------------
# Group member scanning via modelspace walk
# ---------------------------------------------------------------------------


def _find_role_oid(
    db: Db.Database, group_guid: str, target_role: str
) -> Db.ObjectId | None:
    """Scan modelspace for entity with matching group_guid and role."""
    try:
        ms = Db.BlockTableRecord(db.modelSpaceId(), Db.OpenMode.kForRead)
        for oid in ms.objectIds():
            try:
                ent = Db.Entity(oid, Db.OpenMode.kForRead)
                if not ent.isDerivedFrom(Db.Curve.desc()):
                    ent.close()
                    continue
                xd = _read_xdata(ent)
                if xd is None:
                    ent.close()
                    continue
                g = _xdata_get_str(xd, 3)
                r = _xdata_get_str(xd, 2)
                ent.close()
                if g == group_guid and r == target_role:
                    return oid
            except Exception:
                pass
        ms.close()
    except Exception:
        pass
    return None


def _find_stroke_oids_in_group(
    db: Db.Database, group_guid: str
) -> list[Db.ObjectId]:
    """Find all stroke ObjectIds for a group."""
    result: list[Db.ObjectId] = []
    try:
        ms = Db.BlockTableRecord(db.modelSpaceId(), Db.OpenMode.kForRead)
        for oid in ms.objectIds():
            try:
                ent = Db.Entity(oid, Db.OpenMode.kForRead)
                if not ent.isDerivedFrom(Db.Curve.desc()):
                    ent.close()
                    continue
                xd = _read_xdata(ent)
                if xd is None:
                    ent.close()
                    continue
                g = _xdata_get_str(xd, 3)
                r = _xdata_get_str(xd, 2)
                ent.close()
                if g == group_guid and r == ROLE_STROKE:
                    result.append(oid)
            except Exception:
                pass
        ms.close()
    except Exception:
        pass
    return result


def _erase_strokes_in_group(db: Db.Database, group_guid: str) -> int:
    """Erase all stroke entities for a group. Returns count."""
    oids = _find_stroke_oids_in_group(db, group_guid)
    for oid in oids:
        try:
            ent = Db.Entity(oid, Db.OpenMode.kForWrite)
            ent.erase()
            ent.close()
        except Exception:
            pass
    return len(oids)


# ---------------------------------------------------------------------------
# Read stroke handles from Top extension dict (tr-less helper)
# ---------------------------------------------------------------------------


def _top_read_stroke_handles(
    db: Db.Database, top_oid: Db.ObjectId
) -> list[str] | None:
    """Open a short-lived transaction to read stroke handles from Top."""
    try:
        mgr = db.transactionManager()
        tr = mgr.startTransaction()
        try:
            result = _xread_stroke_handles(tr, top_oid)
            mgr.abortTransaction()
            return result
        except Exception:
            mgr.abortTransaction()
            return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# IGI_SLOPE (create)
# ---------------------------------------------------------------------------


@command(name="IGI_SLOPE")
def slope_create() -> None:
    """Create slope strokes between two curves."""
    try:
        print("\n[IGI Tools] === Построение откоса ===")

        db = Db.curDb()

        # ── Load settings ──
        saved = _load_settings()
        saved.setdefault("step", _DEFAULT_STEP)
        saved.setdefault("bottom_offset", _DEFAULT_BOTTOM_OFFSET)
        saved.setdefault("short_count", _DEFAULT_SHORT_COUNT)
        saved.setdefault("use_mid_length", _DEFAULT_USE_MID_LENGTH)
        saved.setdefault("mid_ratio", _DEFAULT_MID_RATIO)
        saved.setdefault("mid_length", _DEFAULT_MID_LENGTH)
        saved.setdefault("layer", _DEFAULT_LAYER)

        # ── Dialog ──
        result = _show_dialog(saved)
        if result is None or result.get("action") != "ok":
            print("\n[IGI Tools] Отменено пользователем.")
            return

        step = result["step"]
        bottom_offset = result["bottom_offset"]
        short_count = result["short_count"]
        use_mid_length = result["use_mid_length"]
        mid_ratio = result["mid_ratio"]
        mid_length = result["mid_length"]
        layer_name = result["layer"]

        print(
            f"\n[IGI Tools] Параметры: шаг={step}, отступ={bottom_offset}, "
            f"shortCount={short_count}, useMid={use_mid_length}, "
            f"midRatio={mid_ratio}, midLength={mid_length}, слой={layer_name}"
        )

        # ── Select top curve ──
        status, top_oid, err = _select_curve("\nВыберите верхний контур откоса: ")
        if status != Ed.PromptStatus.eOk:
            if status != Ed.PromptStatus.eCancel:
                print(f"\n[IGI Tools] Ошибка: {err}")
            return

        # ── Select bottom curve ──
        status, bot_oid, err = _select_curve("\nВыберите нижний контур откоса: ")
        if status != Ed.PromptStatus.eOk:
            if status != Ed.PromptStatus.eCancel:
                print(f"\n[IGI Tools] Ошибка: {err}")
            return

        # ── Validation ──
        if top_oid == bot_oid:
            print("\n[IGI Tools] Верхний и нижний контуры — один и тот же объект.")
            return

        top_curve, bot_curve = _get_curves_from_oids(top_oid, bot_oid)
        if top_curve is None or bot_curve is None:
            print("\n[IGI Tools] Не удалось открыть контуры.")
            return

        top_closed = top_curve.isClosed()
        bot_closed = bot_curve.isClosed()
        if top_closed != bot_closed:
            _close_curves(top_curve, bot_curve)
            print("\n[IGI Tools] Оба контура должны быть либо замкнутыми, либо разомкнутыми.")
            return

        # ── Ensure regapp and layer ──
        _ensure_regapp(db)
        layer_id = _ensure_layer(db, layer_name)

        # ── Prepare projected curves ──
        ucs_origin = Ed.Editor.getCurrentUCS().origin()
        plane_normal = Ed.Editor.ucsNormalVector()
        ucs_plane = Ge.Plane(ucs_origin, plane_normal)

        try:
            f_top = top_curve.getOrthoProjectedCurve(ucs_plane)
        except Exception:
            f_top = Db.Curve.cloneFrom(top_curve)

        try:
            f_bottom = bot_curve.getOrthoProjectedCurve(ucs_plane)
        except Exception:
            f_bottom = Db.Curve.cloneFrom(bot_curve)

        # Close originals before transaction
        _close_curves(top_curve, bot_curve)

        # ── Compute lengths ──
        Lt = _get_curve_length(f_top)
        Lb = _get_curve_length(f_bottom)

        # ── Phase alignment for closed curves ──
        if top_closed:
            cw_top = _get_clockwise_order(f_top)
            cw_bot = _get_clockwise_order(f_bottom)
            if cw_top != cw_bot and cw_top != 0 and cw_bot != 0:
                f_bottom.reverseCurve()
                Lb = _get_curve_length(f_bottom)

            phi = _find_best_phase_shift(f_top, f_bottom, 360)
            if phi > 0.0:
                f_bottom = _shift_curve_start(f_bottom, phi * Lb)
                Lb = _get_curve_length(f_bottom)

        if _should_reverse_curve(f_top, f_bottom):
            f_bottom.reverseCurve()
            Lb = _get_curve_length(f_bottom)

        # ── Find intersection range (two extreme points) ──
        top_offset = 0.0
        bot_offset = 0.0
        ir = _find_intersection_range(f_top, f_bottom)
        if ir is not None:
            top_start, top_end, bot_start, bot_end, need_reverse_bot = ir
            if need_reverse_bot:
                f_bottom.reverseCurve()
                Lb = _get_curve_length(f_bottom)
                bot_start, bot_end = Lb - bot_end, Lb - bot_start
            Lt_range = top_end - top_start
            Lb_range = bot_end - bot_start
            if Lt_range >= step and Lb_range >= step:
                print(f"[IGI Tools] Диапазон откоса между точками пересечений: "
                      f"top={top_start:.2f}..{top_end:.2f}, "
                      f"bot={bot_start:.2f}..{bot_end:.2f}")
                top_offset = top_start
                bot_offset = bot_start
                Lt = Lt_range
                Lb = Lb_range
            else:
                print(f"[IGI Tools] Диапазон пересечений меньше шага — обрезка не применяется.")

        # ── Determine stroke count ──
        total_strokes = max(3, int(round(Lt / step)) + 1) if top_closed else max(
            2, int(round(Lt / step)) + 1
        )

        if not _check_min_strokes(total_strokes, short_count, top_closed):
            print("\n[IGI Tools] Слишком мало штрихов для выбранной схемы.")
            return

        top_step_i = Lt / (total_strokes - 1) if total_strokes > 1 else Lt
        bot_step_i = Lb / (total_strokes - 1) if total_strokes > 1 else Lb

        # ── Build stroke point pairs ──
        top_pts: list[Ge.Point3d] = []
        bot_pts: list[Ge.Point3d] = []

        for i in range(total_strokes):
            td = min(top_offset + top_step_i * i, top_offset + Lt - 1e-10)
            bd = min(bot_offset + bot_step_i * i, bot_offset + Lb - 1e-10)

            tp = f_top.getPointAtDist(td)
            bp = f_bottom.getPointAtDist(bd)

            # Project back to 3D using original curve OIDs
            te = Db.Entity(top_oid, Db.OpenMode.kForRead)
            tc = Db.Curve.cast(te)
            if tc is not None:
                try:
                    tp_3d = tc.getClosestPointTo(tp, plane_normal, False)
                except Exception:
                    tp_3d = tp
                tc.close()
            else:
                tp_3d = tp

            be_ent = Db.Entity(bot_oid, Db.OpenMode.kForRead)
            bc = Db.Curve.cast(be_ent)
            if bc is not None:
                try:
                    bp_3d = bc.getClosestPointTo(bp, plane_normal, False)
                except Exception:
                    bp_3d = bp
                bc.close()
            else:
                bp_3d = bp

            top_pts.append(tp_3d)
            bot_pts.append(bp_3d)

        # ── Create strokes in transaction ──
        group_guid = _new_group_guid()
        top_handle_str = top_oid.handle().toString()
        bot_handle_str = bot_oid.handle().toString()

        stroke_handles: list[str] = []

        mgr = db.transactionManager()
        tr = mgr.startTransaction()
        try:
            for i in range(total_strokes):
                is_short = _is_short_stroke(i, short_count)
                end_pt = _compute_stroke_end(
                    top_pts[i],
                    bot_pts[i],
                    is_short,
                    bottom_offset,
                    mid_ratio,
                    use_mid_length,
                    mid_length,
                )

                model = Db.BlockTableRecord(
                    db.modelSpaceId(), Db.OpenMode.kForWrite
                )
                line = Db.Line(top_pts[i], end_pt)
                line.setDatabaseDefaults(db)
                line.setLayer(layer_id)
                line.setColorIndex(0)  # ByBlock
                lt = Db.LinetypeTable(db.linetypeTableId(), Db.OpenMode.kForRead)
                continuous_lt_id = lt.getAt("Continuous")
                lt.close()
                line.setLinetype(continuous_lt_id)  # Continuous
                line.setLinetypeScale(0.5)
                line.setLineWeight(Db.LineWeight.kLnWt015)  # 0.15 mm
                line.setXData(
                    _make_stroke_xdata(
                        group_guid, layer_name, i, is_short, top_handle_str,
                    )
                )
                model.appendAcDbEntity(line)
                model.close()
                stroke_handles.append(line.objectId().handle().toString())

            # Top XData
            top_ent = tr.getObject(top_oid, Db.OpenMode.kForWrite)
            top_ent.setXData(
                _make_top_xdata(
                    group_guid,
                    total_strokes,
                    bottom_offset,
                    short_count,
                    mid_ratio,
                    use_mid_length,
                    mid_length,
                    bot_handle_str,
                )
            )

            # Bottom XData
            bot_ent = tr.getObject(bot_oid, Db.OpenMode.kForWrite)
            bot_ent.setXData(_make_bottom_xdata(group_guid, top_handle_str))

            # Stroke handles Xrecord
            _xwrite_stroke_handles(tr, top_oid, stroke_handles)

            mgr.endTransaction()
        except Exception:
            mgr.abortTransaction()
            raise

        _save_settings(
            {
                "step": step,
                "bottom_offset": bottom_offset,
                "short_count": short_count,
                "use_mid_length": use_mid_length,
                "mid_ratio": mid_ratio,
                "mid_length": mid_length,
                "layer": layer_name,
            }
        )

        print(f"\n[IGI Tools] Откос построен: {len(stroke_handles)} штрихов.")

    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")


# ---------------------------------------------------------------------------
# IGI_SLOPE_EDIT
# ---------------------------------------------------------------------------


@command(name="IGI_SLOPE_EDIT")
def slope_edit() -> None:
    """Edit an existing slope group — rebuild strokes with new params."""
    try:
        print("\n[IGI Tools] === Редактирование откоса ===")

        db = Db.curDb()

# ── Select stroke ──
        res, oid, _ = Ed.Editor.entSel("\nВыберите штрих откоса для редактирования: ")
        if res != Ed.PromptStatus.eOk:
            return

        ent = Db.Entity(oid, Db.OpenMode.kForRead)
        xd = _read_xdata(ent)
        if xd is None:
            ent.close()
            print("\n[IGI Tools] Объект не принадлежит группе откоса.")
            return
        role = _xdata_get_str(xd, 2)
        if role != ROLE_STROKE:
            ent.close()
            print("\n[IGI Tools] Выберите штрих откоса, а не контур.")
            return
        group_guid = _xdata_get_str(xd, 3)
        ent.close()

        if group_guid is None:
            print("\n[IGI Tools] Отсутствует GUID группы.")
            return

        print(f"\n[IGI Tools] Группа: {group_guid[:8]}…")

        # ── Find Top ──
        top_oid = _find_role_oid(db, group_guid, ROLE_TOP)
        if top_oid is None:
            print("\n[IGI Tools] Не удалось найти верхний контур.")
            return
        bot_oid = _find_role_oid(db, group_guid, ROLE_BOTTOM)
        if bot_oid is None:
            print("\n[IGI Tools] Не удалось найти нижний контур.")
            return

        # ── Read saved params from Top XData ──
        te = Db.Entity(top_oid, Db.OpenMode.kForRead)
        txd = _read_xdata(te)
        if txd is None:
            te.close()
            print("\n[IGI Tools] Верхний контур без XData откоса.")
            return

        total_original = _xdata_get_int(txd, 4)  # num_strokes from creation
        bottom_offset = _xdata_get_double(txd, 5) or _DEFAULT_BOTTOM_OFFSET
        short_count = _xdata_get_int(txd, 6) or _DEFAULT_SHORT_COUNT
        use_mid_length = bool(_xdata_get_int(txd, 8) or _DEFAULT_USE_MID_LENGTH)
        mid_ratio = _xdata_get_double(txd, 7) or _DEFAULT_MID_RATIO
        mid_length = _xdata_get_double(txd, 9) or _DEFAULT_MID_LENGTH

        # Try reading layer from first stroke
        stroke_handles = _top_read_stroke_handles(db, top_oid)
        layer_name = _DEFAULT_LAYER
        if stroke_handles:
            soid = _try_get_oid_by_handle(db, stroke_handles[0])
            if soid is not None:
                try:
                    se = Db.Entity(soid, Db.OpenMode.kForRead)
                    sx = _read_xdata(se)
                    if sx:
                        lyr = _xdata_get_str(sx, 4)
                        if lyr:
                            layer_name = lyr
                    se.close()
                except Exception:
                    pass
        te.close()

        # ── Build stroke data for Jig ──

        # Open top/bottom curves for geometry
        top_curve_raw = Db.Entity(top_oid, Db.OpenMode.kForRead)
        top_curve = Db.Curve.cast(top_curve_raw)
        bot_curve_raw = Db.Entity(bot_oid, Db.OpenMode.kForRead)
        bot_curve = Db.Curve.cast(bot_curve_raw)
        if top_curve is None or bot_curve is None:
            print("\n[IGI Tools] Контуры не являются кривыми.")
            return

        bot_len = _get_curve_length(bot_curve)

        # ── Project curves for intersection check ──
        ucs_origin = Ed.Editor.getCurrentUCS().origin()
        plane_normal = Ed.Editor.ucsNormalVector()
        ucs_plane = Ge.Plane(ucs_origin, plane_normal)
        try:
            f_top_edit = top_curve.getOrthoProjectedCurve(ucs_plane)
        except Exception:
            f_top_edit = Db.Curve.cloneFrom(top_curve)
        try:
            f_bot_edit = bot_curve.getOrthoProjectedCurve(ucs_plane)
        except Exception:
            f_bot_edit = Db.Curve.cloneFrom(bot_curve)

        # ── Find intersection range for filtering existing strokes ──
        ir = _find_intersection_range(f_top_edit, f_bot_edit)
        clip_bot_start: float | None = None
        clip_bot_end: float | None = None
        if ir is not None:
            _, _, clip_bot_start, clip_bot_end, _ = ir
            print(f"[IGI Tools] Диапазон пересечений на нижнем контуре: "
                  f"{clip_bot_start:.2f}..{clip_bot_end:.2f}. "
                  f"Штрихи вне диапазона будут исключены.")

        # Find all stroke OIDs by scanning modelspace (more reliable than Xrecord)
        stroke_oids = _find_stroke_oids_in_group(db, group_guid)
        if not stroke_oids:
            print("\n[IGI Tools] Нет штрихов в группе (сканирование ModelSpace).")
            top_curve.close()
            bot_curve.close()
            return

        # Build (index, OID, top_pt, bottom_dist, end_pt) for each stroke.
        # bottom_dist is the REAL distance along the bottom curve at the line's end.
        # For long strokes end_pt is on/near bottom curve; for short strokes we
        # project end_pt onto bottom curve to get the true parametric position.
        stroke_infos: list[tuple[int, Db.ObjectId, Ge.Point3d, float, Ge.Point3d]] = []
        for s_oid in stroke_oids:
            try:
                line = Db.Entity(s_oid, Db.OpenMode.kForRead)
                line_curve = Db.Curve.cast(line)
                if line_curve is None:
                    line.close()
                    continue
                line_xdata = _read_xdata(line)
                if line_xdata is None:
                    line.close()
                    continue
                idx = _xdata_get_int(line_xdata, 5)
                if idx is None:
                    line.close()
                    continue
                top_pt = line_curve.getStartPoint()
                end_pt = line_curve.getEndPoint()

                try:
                    # Project end_pt onto bottom curve — this naturally gives
                    # the parametric position for both long and short strokes.
                    bp_on_bot = bot_curve.getClosestPointTo(end_pt, False)
                    bot_dist = bot_curve.getDistAtPoint(bp_on_bot)
                except Exception:
                    bot_dist = 0.0

                stroke_infos.append((idx, s_oid, top_pt, bot_dist, end_pt))
                line.close()
            except Exception:
                pass

        stroke_infos.sort(key=lambda x: x[0])

        # ── Filter strokes outside intersection range ──
        if clip_bot_start is not None and clip_bot_end is not None:
            bot_range = clip_bot_end - clip_bot_start
            if bot_range < bot_len * 0.01:
                print(f"[IGI Tools]   Диапазон слишком мал ({bot_range:.2f}) — фильтрация отключена.")
            else:
                stroke_infos = [
                    si for si in stroke_infos
                    if clip_bot_start - 1e-8 <= si[3] <= clip_bot_end + 1e-8
                ]
            if not stroke_infos:
                print("\n[IGI Tools] Все штрихи оказались вне диапазона пересечения контуров.")
                top_curve.close()
                bot_curve.close()
                return

        total_strokes = len(stroke_infos)
        top_pts = [s[2] for s in stroke_infos]
        orig_bot_dists = [s[3] for s in stroke_infos]

        # Step from XData (stored in num_strokes slot) – estimate from existing strokes
        step = bot_len / max(total_strokes - 1, 1) if total_strokes > 1 else 1.0

        # Find selected stroke by ObjectId (from entSel)
        sel_array_idx = next(
            (i for i, s in enumerate(stroke_infos) if s[1] == oid),
            None,
        )
        if sel_array_idx is None:
            print("\n[IGI Tools] Выбранный штрих не найден среди штрихов группы.")
            top_curve.close()
            bot_curve.close()
            return

        # ── Modeless slider dialog (radius + power) ──
        from igi_tools.commands.slope.ui import _RadiusEditSlider
        from igi_tools.commands.slope.jig import SlopeEditJig

        import wx
        res_override = Ap.ResourceOverride()
        is_closed = top_curve.isClosed()
        radius_dlg = _RadiusEditSlider(total_strokes, sel_array_idx, is_closed)
        radius_dlg.Show()
        wx.Yield()

        jig = SlopeEditJig(
            top_curve, bot_curve,
            top_pts, orig_bot_dists,
            sel_array_idx, bot_len, total_strokes,
            step, bottom_offset, short_count,
            use_mid_length, mid_ratio, mid_length,
            plane_normal,
            radius_dlg=radius_dlg,
        )
        drag_status = jig.drag()

        # Close curves + dialog
        radius_dlg.Destroy()
        del res_override
        top_curve.close()
        bot_curve.close()

        if drag_status != Ed.DragStatus.kNormal:
            print("\n[IGI Tools] Редактирование отменено.")
            return

        # ── Apply: erase old, create new, update XData ──
        _erase_strokes_in_group(db, group_guid)

        # Get final end points from Jig
        new_end_pts = jig.get_new_end_pts()
        if not new_end_pts or len(new_end_pts) != total_strokes:
            print("\n[IGI Tools] Не удалось получить результат редактирования.")
            return

        # Read new bottom distances from Jig
        new_bot_dists = jig.get_new_bottom_dists()

        mgr = db.transactionManager()
        tr = mgr.startTransaction()
        try:
            _ensure_regapp(db)
            layer_id = _ensure_layer(db, layer_name)
            top_handle_str = top_oid.handle().toString()
            bot_handle_str = bot_oid.handle().toString()
            new_stroke_handles: list[str] = []

            for i in range(total_strokes):
                is_short = _is_short_stroke(i, short_count)
                end_pt = new_end_pts[i]

                model = Db.BlockTableRecord(db.modelSpaceId(), Db.OpenMode.kForWrite)
                line = Db.Line(top_pts[i], end_pt)
                line.setDatabaseDefaults(db)
                line.setLayer(layer_id)
                line.setColorIndex(0)  # ByBlock
                lt = Db.LinetypeTable(db.linetypeTableId(), Db.OpenMode.kForRead)
                continuous_lt_id = lt.getAt("Continuous")
                lt.close()
                line.setLinetype(continuous_lt_id)  # Continuous
                line.setLinetypeScale(0.5)
                line.setLineWeight(Db.LineWeight.kLnWt015)  # 0.15 mm
                line.setXData(
                    _make_stroke_xdata(
                        group_guid, layer_name, i, is_short, top_handle_str,
                    )
                )
                model.appendAcDbEntity(line)
                model.close()
                new_stroke_handles.append(line.objectId().handle().toString())

            # Update Top XData
            top_ent = tr.getObject(top_oid, Db.OpenMode.kForWrite)
            top_ent.setXData(
                _make_top_xdata(
                    group_guid, total_strokes, bottom_offset, short_count,
                    mid_ratio, use_mid_length, mid_length, bot_handle_str,
                )
            )

            # Update Bottom XData
            bot_ent = tr.getObject(bot_oid, Db.OpenMode.kForWrite)
            bot_ent.setXData(_make_bottom_xdata(group_guid, top_handle_str))

            # Update Xrecord
            _xwrite_stroke_handles(tr, top_oid, new_stroke_handles)

            mgr.endTransaction()
        except Exception:
            mgr.abortTransaction()
            raise

        print(f"\n[IGI Tools] Откос отредактирован: {total_strokes} штрихов.")

    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")


# ---------------------------------------------------------------------------
# IGI_SLOPE_DELETE
# ---------------------------------------------------------------------------


@command(name="IGI_SLOPE_DELETE")
def slope_delete() -> None:
    """Delete an existing slope group."""
    try:
        print("\n[IGI Tools] === Удаление откоса ===")

        db = Db.curDb()

        res, oid, _ = Ed.Editor.entSel("\nВыберите элемент откоса для удаления: ")
        if res != Ed.PromptStatus.eOk:
            return

        ent = Db.Entity(oid, Db.OpenMode.kForRead)
        xd = _read_xdata(ent)
        if xd is None:
            ent.close()
            print("\n[IGI Tools] Объект не является частью откоса.")
            return
        role = _xdata_get_str(xd, 2)
        if role not in (ROLE_TOP, ROLE_BOTTOM, ROLE_STROKE):
            ent.close()
            print("\n[IGI Tools] Неопознанная роль.")
            return
        group_guid = _xdata_get_str(xd, 3)
        ent.close()

        if group_guid is None:
            print("\n[IGI Tools] Отсутствует GUID группы.")
            return

        top_oid = _find_role_oid(db, group_guid, ROLE_TOP)

        cnt = _erase_strokes_in_group(db, group_guid)
        print(f"\n[IGI Tools] Стерто штрихов: {cnt}")

        if top_oid is not None:
            mgr = db.transactionManager()
            tr = mgr.startTransaction()
            try:
                top_ent = tr.getObject(top_oid, Db.OpenMode.kForWrite)
                _clear_xdata(top_ent)
                _remove_stroke_handles(tr, top_oid)
                mgr.endTransaction()
            except Exception:
                mgr.abortTransaction()

        print("\n[IGI Tools] Откос удалён.")

    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")


# ---------------------------------------------------------------------------
# Rebuild slope (shared by IGI_SLOPE_EDIT)
# ---------------------------------------------------------------------------


def _rebuild_slope(
    db: Db.Database,
    top_oid: Db.ObjectId,
    bot_oid: Db.ObjectId,
    group_guid: str,
    step: float,
    bottom_offset: float,
    short_count: int,
    use_mid_length: bool,
    mid_ratio: float,
    mid_length: float,
    layer_name: str,
) -> None:
    """Rebuild slope strokes with given parameters."""
    ucs_origin = Ed.Editor.getCurrentUCS().origin()
    plane_normal = Ed.Editor.ucsNormalVector()
    ucs_plane = Ge.Plane(ucs_origin, plane_normal)

    # ── Open originals for geometry extraction ──
    top_curve, bot_curve = _get_curves_from_oids(top_oid, bot_oid)
    if top_curve is None or bot_curve is None:
        print("[IGI Tools] Не удалось открыть контуры.")
        return

    top_closed = top_curve.isClosed()

    try:
        f_top = top_curve.getOrthoProjectedCurve(ucs_plane)
    except Exception:
        f_top = Db.Curve.cloneFrom(top_curve)
    try:
        f_bottom = bot_curve.getOrthoProjectedCurve(ucs_plane)
    except Exception:
        f_bottom = Db.Curve.cloneFrom(bot_curve)

    _close_curves(top_curve, bot_curve)

    _ensure_regapp(db)
    layer_id = _ensure_layer(db, layer_name)

    Lt = _get_curve_length(f_top)
    Lb = _get_curve_length(f_bottom)

    # Phase alignment
    if top_closed:
        cw_top = _get_clockwise_order(f_top)
        cw_bot = _get_clockwise_order(f_bottom)
        if cw_top != cw_bot and cw_top != 0 and cw_bot != 0:
            f_bottom.reverseCurve()
            Lb = _get_curve_length(f_bottom)
        phi = _find_best_phase_shift(f_top, f_bottom, 360)
        if phi > 0.0:
            f_bottom = _shift_curve_start(f_bottom, phi * Lb)
            Lb = _get_curve_length(f_bottom)

    if _should_reverse_curve(f_top, f_bottom):
        f_bottom.reverseCurve()
        Lb = _get_curve_length(f_bottom)

    # ── Find intersection range (two extreme points) ──
    top_offset = 0.0
    bot_offset = 0.0
    ir = _find_intersection_range(f_top, f_bottom)
    if ir is not None:
        top_start, top_end, bot_start, bot_end, need_reverse_bot = ir
        if need_reverse_bot:
            f_bottom.reverseCurve()
            Lb = _get_curve_length(f_bottom)
            bot_start, bot_end = Lb - bot_end, Lb - bot_start
        Lt_range = top_end - top_start
        Lb_range = bot_end - bot_start
        if Lt_range >= step and Lb_range >= step:
            print(f"[IGI Tools] Диапазон откоса между точками пересечений: "
                  f"top={top_start:.2f}..{top_end:.2f}, "
                  f"bot={bot_start:.2f}..{bot_end:.2f}")
            top_offset = top_start
            bot_offset = bot_start
            Lt = Lt_range
            Lb = Lb_range
        else:
            print(f"[IGI Tools] Диапазон пересечений меньше шага — обрезка не применяется.")

    total_strokes = max(3, int(round(Lt / step)) + 1) if top_closed else max(
        2, int(round(Lt / step)) + 1
    )
    if not _check_min_strokes(total_strokes, short_count, top_closed):
        return

    top_step_i = Lt / (total_strokes - 1) if total_strokes > 1 else Lt
    bot_step_i = Lb / (total_strokes - 1) if total_strokes > 1 else Lb

    top_handle_str = top_oid.handle().toString()
    bot_handle_str = bot_oid.handle().toString()

    stroke_handles: list[str] = []

    mgr = db.transactionManager()
    tr = mgr.startTransaction()
    try:
        for i in range(total_strokes):
            td = min(top_offset + top_step_i * i, top_offset + Lt - 1e-10)
            bd = min(bot_offset + bot_step_i * i, bot_offset + Lb - 1e-10)
            tp = f_top.getPointAtDist(td)
            bp = f_bottom.getPointAtDist(bd)

            # Project to 3D
            te = Db.Entity(top_oid, Db.OpenMode.kForRead)
            tc = Db.Curve.cast(te)
            if tc is not None:
                try:
                    tp_3d = tc.getClosestPointTo(tp, plane_normal, False)
                except Exception:
                    tp_3d = tp
                tc.close()
            else:
                tp_3d = tp

            be = Db.Entity(bot_oid, Db.OpenMode.kForRead)
            bc = Db.Curve.cast(be)
            if bc is not None:
                try:
                    bp_3d = bc.getClosestPointTo(bp, plane_normal, False)
                except Exception:
                    bp_3d = bp
                bc.close()
            else:
                bp_3d = bp

            is_short = _is_short_stroke(i, short_count)
            end_pt = _compute_stroke_end(
                tp_3d, bp_3d, is_short,
                bottom_offset, mid_ratio, use_mid_length, mid_length,
            )

            model = Db.BlockTableRecord(db.modelSpaceId(), Db.OpenMode.kForWrite)
            line = Db.Line(tp_3d, end_pt)
            line.setDatabaseDefaults(db)
            line.setLayer(layer_id)
            line.setColorIndex(0)  # ByBlock
            lt = Db.LinetypeTable(db.linetypeTableId(), Db.OpenMode.kForRead)
            continuous_lt_id = lt.getAt("Continuous")
            lt.close()
            line.setLinetype(continuous_lt_id)  # Continuous
            line.setLinetypeScale(0.5)
            line.setLineWeight(Db.LineWeight.kLnWt015)  # 0.15 mm
            line.setXData(
                _make_stroke_xdata(
                    group_guid, layer_name, i, is_short, top_handle_str,
                )
            )
            model.appendAcDbEntity(line)
            model.close()
            stroke_handles.append(line.objectId().handle().toString())

        # Top XData rewrite
        top_ent = tr.getObject(top_oid, Db.OpenMode.kForWrite)
        top_ent.setXData(
            _make_top_xdata(
                group_guid, total_strokes, bottom_offset, short_count,
                mid_ratio, use_mid_length, mid_length, bot_handle_str,
            )
        )

        # Bottom XData rewrite
        bot_ent = tr.getObject(bot_oid, Db.OpenMode.kForWrite)
        bot_ent.setXData(_make_bottom_xdata(group_guid, top_handle_str))

        # Stroke handles Xrecord
        _xwrite_stroke_handles(tr, top_oid, stroke_handles)

        mgr.endTransaction()
    except Exception:
        mgr.abortTransaction()
        raise
