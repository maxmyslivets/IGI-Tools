"""Выравнивание текста блоков СП_9.2, СП_6.5.2 вдоль опорной линии.

Алгоритм:
1. Выбор отрезков/полилиний/3D-полилиний и блоков одним набором.
2. Для каждого блока — поиск ближайшего сегмента опорной кривой.
3. Расчёт угла касательной сегмента.
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
    if angle < 0:
        angle += 2 * math.pi

    if angle > math.pi / 2:
        angle -= math.pi
    elif angle <= -math.pi / 2:
        angle += math.pi

    return angle


def _project_onto_segment(
    pt: Ge.Point3d, s0: Ge.Point3d, s1: Ge.Point3d,
) -> tuple[Ge.Point3d, float, float]:
    """Проецирование точки на отрезок.

    Возвращает (точка_проекции, параметр_t [0..1], квадрат_расстояния).
    """
    dx = s1.x - s0.x
    dy = s1.y - s0.y
    dz = s1.z - s0.z
    seg_len_sq = dx * dx + dy * dy + dz * dz

    if seg_len_sq < 1e-12:
        dp = pt - s0
        return s0, 0.0, dp.x * dp.x + dp.y * dp.y + dp.z * dp.z

    t = ((pt.x - s0.x) * dx + (pt.y - s0.y) * dy + (pt.z - s0.z) * dz) / seg_len_sq
    t = max(0.0, min(1.0, t))

    proj = Ge.Point3d(s0.x + t * dx, s0.y + t * dy, s0.z + t * dz)
    dp = pt - proj
    dist_sq = dp.x * dp.x + dp.y * dp.y + dp.z * dp.z
    return proj, t, dist_sq


def _extract_segments(ent: Db.Entity) -> list[tuple[Ge.Point3d, Ge.Point3d, float, float]]:
    """Извлечь отрезки из кривой.

    Возвращает список (start, end, seg_angle, seg_length_sq).
    seg_angle = atan2(dy, dx) в плоскости XY.
    """
    segments: list[tuple[Ge.Point3d, Ge.Point3d, float, float]] = []

    if ent.isDerivedFrom(Db.Line.desc()):
        line = Db.Line.cast(ent)
        p0 = line.startPoint()
        p1 = line.endPoint()
        dx = p1.x - p0.x
        dy = p1.y - p0.y
        angle = math.atan2(dy, dx)
        seg_len_sq = dx * dx + dy * dy
        segments.append((p0, p1, angle, seg_len_sq))

    elif ent.isDerivedFrom(Db.Polyline.desc()):
        pline = Db.Polyline.cast(ent)
        n = pline.numVerts()
        pts = [pline.getPointAtParam(float(i)) for i in range(n)]
        for i in range(n - 1):
            dx = pts[i + 1].x - pts[i].x
            dy = pts[i + 1].y - pts[i].y
            angle = math.atan2(dy, dx)
            seg_len_sq = dx * dx + dy * dy
            segments.append((pts[i], pts[i + 1], angle, seg_len_sq))
        if n >= 3 and pline.isClosed():
            dx = pts[0].x - pts[-1].x
            dy = pts[0].y - pts[-1].y
            angle = math.atan2(dy, dx)
            seg_len_sq = dx * dx + dy * dy
            segments.append((pts[-1], pts[0], angle, seg_len_sq))

    elif ent.isDerivedFrom(Db.Polyline3d.desc()):
        pl3d = Db.Polyline3d.cast(ent)
        pts = pl3d.toPoint3dList()
        for i in range(len(pts) - 1):
            dx = pts[i + 1].x - pts[i].x
            dy = pts[i + 1].y - pts[i].y
            angle = math.atan2(dy, dx)
            seg_len_sq = dx * dx + dy * dy
            segments.append((pts[i], pts[i + 1], angle, seg_len_sq))
        # 3D polyline closure is not checked here — rarely closed in practice

    return segments


def _find_best_segment(
    bref_pos: Ge.Point3d,
    all_segments: list[tuple[Ge.Point3d, Ge.Point3d, float, float]],
) -> float | None:
    """Найти ближайший к точке сегмент среди ВСЕХ кривых.

    Возвращает угол для текста. Если блок дальше порога (10 ед.) — None."""
    TOLERANCE_SQ = 100.0  # 10^2 — блок дальше этой дистанции считается не на линии
    best_dist_sq = float("inf")
    best_angle = 0.0

    for s0, s1, seg_angle, seg_len_sq in all_segments:
        if seg_len_sq < 1e-12:
            continue
        _, _, dist_sq = _project_onto_segment(bref_pos, s0, s1)
        if dist_sq < best_dist_sq:
            best_dist_sq = dist_sq
            best_angle = seg_angle

    if best_dist_sq > TOLERANCE_SQ:
        return None

    return _normalize_angle_readable(best_angle)


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
                elif ent.isDerivedFrom(Db.Line.desc()) or ent.isDerivedFrom(Db.Polyline.desc()):
                    # Db.Polyline covers both LWPOLYLINE and POLYLINE (2D)
                    curve_ents.append(ent)
                    curve_count += 1
                elif ent.isDerivedFrom(Db.Polyline3d.desc()):
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

        # ── Step 3: extract all curve segments into one flat list ──
        all_segments: list[tuple[Ge.Point3d, Ge.Point3d, float, float]] = []
        for ent in curve_ents:
            try:
                segs = _extract_segments(ent)
                all_segments.extend(segs)
            except Exception as exc:
                print(f"[IGI Tools] Ошибка извлечения сегментов из кривой: {exc}")
            finally:
                ent.close()

        if not all_segments:
            print("[IGI Tools] Не удалось извлечь сегменты из опорных кривых.")
            return

        # ── Step 4: align each block to the closest segment globally ──
        processed = 0
        errors = 0

        for bref_id, block_name in block_info:
            angle_prop_name = _BLOCK_CONFIG[block_name]
            bref = Db.BlockReference(bref_id, Db.OpenMode.kForRead)
            try:
                pos = bref.position()

                text_angle = _find_best_segment(pos, all_segments)
                if text_angle is None:
                    print(f"[IGI Tools] Блок ({block_name}) на ("
                          f"{pos.x:.2f}, {pos.y:.2f}) — не найден на опорных кривых.")
                    continue

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

        # ── Step 5: summary ──
        print(
            f"\n[IGI Tools] Выровнено блоков: {processed}."
            + (f" Ошибок: {errors}." if errors else "")
        )

    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")