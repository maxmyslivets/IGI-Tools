"""Выравнивание текста блоков СП_9.2, СП_6.5.2 вдоль опорной кривой.

Алгоритм:
1. Выбор отрезков/полилиний и блоков одним набором.
2. Для каждого блока — поиск ближайшей точки на опорной кривой через
   Db.Curve.getClosestPointTo() + getParamAtPoint() + getFirstDeriv().
3. Расчёт угла касательной в найденной точке.
4. Нормализация угла для читаемости (вертикаль → "верх влево").
5. Установка динамических свойств: Положение X=0, Положение Y=0, Угол1=угол.
"""

from __future__ import annotations

import math
import traceback

from pyrx import Ap, Db, Ed, Ge, command

# Конфигурация блоков: имя -> имя свойства угла
_BLOCK_CONFIG: dict[str, str] = {
    "СП_9.2": "Угол1",
    "СП_6.5.2": "Угол",
}


def _normalize_angle_readable(angle: float) -> float:
    """Нормализовать угол для читаемости текста: (-π/2, π/2].

    Для линий, направленных влево/вниз — разворот на 180°.
    Вертикальная линия (π/2) → текст читается снизу вверх, верх букв влево ("верх влево").
    """
    angle = angle % (2 * math.pi)
    if angle > math.pi:
        angle -= 2 * math.pi

    if angle > math.pi / 2:
        angle -= math.pi
    elif angle < -math.pi / 2:
        angle += math.pi

    return angle


def _get_curve_tangent_at_point(curve: Db.Curve, pt: Ge.Point3d) -> tuple[float | None, float]:
    """Найти расстояние от точки до кривой и угол касательной.

    Возвращает (угол_касательной, квадрат_расстояния).
    Если точка вне порога 0.01 — (None, dist_sq).
    """
    TOLERANCE_SQ = 0.0001

    try:
        closest = curve.getClosestPointTo(pt)
    except Exception:
        return None, float("inf")

    if closest is None:
        return None, float("inf")

    dx = pt.x - closest.x
    dy = pt.y - closest.y
    dist_sq = dx * dx + dy * dy

    if dist_sq > TOLERANCE_SQ:
        return None, dist_sq

    try:
        param = curve.getParamAtPoint(closest)
        deriv = curve.getFirstDeriv(param)
    except Exception:
        return None, dist_sq

    if deriv is None:
        return None, dist_sq

    tangent = math.atan2(deriv.y, deriv.x)
    return tangent, dist_sq


@command(name="IGI_ALIGN_SP92", flags=Ap.CmdFlags.USEPICKSET | Ap.CmdFlags.REDRAW)
def align_sp92() -> None:
    """Выравнивание текста блока СП_9.2 вдоль опорной линии."""
    try:
        # ── Step 1: selection ──
        filter_def = [
            (Db.DxfCode.kDxfStart, "LINE"),
            (Db.DxfCode.kDxfStart, "LWPOLYLINE"),
            (Db.DxfCode.kDxfStart, "POLYLINE"),
            (Db.DxfCode.kDxfStart, "INSERT"),
        ]

        block_names_str = ", ".join(sorted(_BLOCK_CONFIG))

        impl_status, impl_ss = Ed.Editor.selectImplied()
        if impl_status == Ed.PromptStatus.eOk and impl_ss.size() > 0:
            all_ids = impl_ss.toList()
        else:
            print(f"\nВыберите линии/полилинии и блоки {block_names_str}...")
            res = Ed.Editor.select(filter_def)
            if res[0] != Ed.PromptStatus.eOk:
                print("[IGI Tools] Выбор отменён.")
                return
            ss = res[1]
            if ss.size() == 0:
                print("[IGI Tools] Объекты не найдены.")
                return
            all_ids = ss.toList()

        # ── Step 2: categorize ──
        curve_ents: list[Db.Entity] = []
        block_info: list[tuple[Db.ObjectId, str]] = []
        block_names_upper = {k.upper(): k for k in _BLOCK_CONFIG}
        curve_count = 0
        block_count = 0
        skipped = 0

        for oid in all_ids:
            ent = Db.Entity(oid, Db.OpenMode.kForRead)
            try:
                if ent.isDerivedFrom(Db.BlockReference.desc()):
                    bref = Db.BlockReference.cast(ent)
                    eff_name = bref.effectiveName()
                    canonical = block_names_upper.get(eff_name.upper())
                    if canonical is not None:
                        block_info.append((oid, canonical))
                        block_count += 1
                    else:
                        skipped += 1
                elif ent.isDerivedFrom(Db.Curve.desc()):
                    # Db.Curve.desc() покрывает Line, Polyline, Polyline2d (PEDIT Fit/Spline),
                    # Polyline3d, Arc, Spline и любые другие наследники AcDbCurve
                    curve_ents.append(ent)
                    curve_count += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1
                ent.close()
                continue

        if not block_info:
            print(f"[IGI Tools] Блоки ({block_names_str}) не найдены среди выбранных.")
            return
        if curve_count == 0:
            print("[IGI Tools] Опорные кривые не найдены среди выбранных.")
            return

        total_skip_msg = f", пропущено прочих объектов: {skipped}" if skipped else ""
        print(
            f"[IGI Tools] Найдено кривых: {curve_count}, "
            f"блоков: {block_count}{total_skip_msg}."
        )

        # ── Step 3: align each block to the closest curve ──
        processed = 0
        errors = 0

        for bref_id, block_name in block_info:
            angle_prop_name = _BLOCK_CONFIG[block_name]
            bref = Db.BlockReference(bref_id, Db.OpenMode.kForRead)
            try:
                pos = bref.position()

                # Find closest curve and its tangent
                best_angle: float | None = None
                best_dist_sq = float("inf")

                for curve_ent in curve_ents:
                    try:
                        curve = Db.Curve.cast(curve_ent)
                        angle, dist_sq = _get_curve_tangent_at_point(curve, pos)
                        if angle is not None and dist_sq < best_dist_sq:
                            best_dist_sq = dist_sq
                            best_angle = angle
                    except Exception:
                        continue

                if best_angle is None:
                    dist = math.sqrt(best_dist_sq)
                    print(f"[IGI Tools] Блок ({block_name}) на ("
                          f"{pos.x:.2f}, {pos.y:.2f}) — пропущен (расстояние {dist:.4f} > 0.01).")
                    continue

                text_angle = _normalize_angle_readable(best_angle)

                # Check dynamic status and collect properties in read mode
                is_dyn = bref.isDynamicBlock()
                dyn_props = bref.getBlockProperties() if is_dyn else None

                # Upgrade to write mode
                bref.upgradeOpen()

                # Apply values
                if is_dyn and dyn_props:
                    has_angle = False
                    for prop in dyn_props:
                        name = prop.propertyName()
                        if name == "Положение X" and not prop.readOnly():
                            prop.setValue(Db.EvalVariant(0.0))
                        elif name == "Положение Y" and not prop.readOnly():
                            prop.setValue(Db.EvalVariant(0.0))
                        elif name == angle_prop_name and not prop.readOnly():
                            prop.setValue(Db.EvalVariant(text_angle))
                            has_angle = True
                    if not has_angle:
                        bref.setRotation(text_angle)
                else:
                    bref.setRotation(text_angle)

                processed += 1

            except Exception as exc:
                print(f"[IGI Tools] Ошибка обработки блока: {exc}")
                errors += 1
            finally:
                bref.close()

        # ── Step 4: close curves ──
        for curve_ent in curve_ents:
            try:
                curve_ent.close()
            except Exception:
                pass

        # ── Step 5: summary ──
        print(
            f"\n[IGI Tools] Выровнено блоков: {processed}."
            + (f" Ошибок: {errors}." if errors else "")
        )

    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")
