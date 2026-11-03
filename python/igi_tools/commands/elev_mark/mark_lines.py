"""Команда IGI_ELEV_MARK_LINES — отметки «СП_9.2» из ЦМР вдоль линий и полилиний."""

from __future__ import annotations

import math
import traceback

from pyrx import Db, Ed, command

from igi_tools import dem
from igi_tools.commands.elev_mark.blocks import ensure_block, insert_mark, reset_marks_stack


def _show_step_dialog() -> float | None:
    """Модальный диалог «Максимальное расстояние между точками». None — отмена."""
    import wx

    class _StepDialog(wx.Dialog):
        def __init__(self):
            wx.Dialog.__init__(
                self,
                None,
                title="IGI Elev Mark Lines — Параметры",
                style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
            )
            self.SetMinSize(wx.Size(360, 150))
            self.result_data: float | None = None

            panel = wx.Panel(self)
            vsizer = wx.BoxSizer(wx.VERTICAL)

            vsizer.Add(
                wx.StaticText(panel, label="Максимальное расстояние между точками (м):"),
                flag=wx.BOTTOM,
                border=6,
            )
            self.step_ctrl = wx.TextCtrl(panel, value="20.0")
            vsizer.Add(self.step_ctrl, flag=wx.EXPAND | wx.BOTTOM, border=12)

            btn_row = wx.BoxSizer(wx.HORIZONTAL)
            btn_row.Add(wx.Button(panel, wx.ID_OK, label="Выполнить"), flag=wx.RIGHT, border=8)
            btn_row.Add(wx.Button(panel, wx.ID_CANCEL, label="Отмена"))
            vsizer.Add(btn_row, flag=wx.ALIGN_CENTER)

            panel.SetSizer(vsizer)
            vsizer.Fit(panel)
            self.Fit()

    dlg = _StepDialog()
    try:
        if dlg.ShowModal() != wx.ID_OK:
            return None
        try:
            value = float(dlg.step_ctrl.GetValue().replace(",", "."))
        except ValueError:
            value = 20.0
        return round(max(0.5, value), 1)
    finally:
        dlg.Destroy()


def _arc_points(
    p1: tuple[float, float],
    p2: tuple[float, float],
    bulge: float,
    max_step: float,
) -> list[tuple[float, float]]:
    """Промежуточные точки дуги сегмента (формулы get_arc_points из референса)."""
    points: list[tuple[float, float]] = []
    x1, y1 = p1
    x2, y2 = p2

    chord = math.hypot(x2 - x1, y2 - y1)
    if chord < 0.001:
        return points

    alpha = 4 * math.atan(abs(bulge))
    radius = chord / (2 * math.sin(alpha / 2))
    sagitta = (chord / 2) * abs(bulge)
    dist_to_center = radius - sagitta

    cx_chord = (x1 + x2) / 2
    cy_chord = (y1 + y2) / 2
    dx = (x2 - x1) / chord
    dy = (y2 - y1) / chord

    if bulge > 0:
        cx = cx_chord - dy * dist_to_center
        cy = cy_chord + dx * dist_to_center
    else:
        cx = cx_chord + dy * dist_to_center
        cy = cy_chord - dx * dist_to_center

    start_angle = math.atan2(y1 - cy, x1 - cx)
    end_angle = math.atan2(y2 - cy, x2 - cx)
    angle_diff = end_angle - start_angle

    if bulge > 0:
        if angle_diff <= 0:
            angle_diff += 2 * math.pi
    else:
        if angle_diff >= 0:
            angle_diff -= 2 * math.pi

    arc_len = radius * abs(angle_diff)
    num_divisions = math.ceil(arc_len / max_step)

    for j in range(1, num_divisions):
        t = j / num_divisions
        curr_angle = start_angle + angle_diff * t
        points.append((cx + radius * math.cos(curr_angle), cy + radius * math.sin(curr_angle)))

    return points


def _linear_points(
    p1: tuple[float, float],
    p2: tuple[float, float],
    max_step: float,
) -> list[tuple[float, float]]:
    """Промежуточные точки прямого сегмента (концевые не входят)."""
    points: list[tuple[float, float]] = []
    seg_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    if seg_len > max_step:
        num_divisions = math.ceil(seg_len / max_step)
        for j in range(1, num_divisions):
            t = j / num_divisions
            points.append((p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t))
    return points


def _polyline_points(
    ent: Db.Entity, max_step: float
) -> list[tuple[float, float]]:
    """Точки вдоль полилинии: вершины и промежуточные по шагу (как в get_line)."""
    pl = Db.Polyline.cast(ent)
    num_verts = pl.numVerts()
    if num_verts < 2:
        return []
    is_closed = pl.isClosed()
    num_segments = num_verts if is_closed else num_verts - 1

    points: list[tuple[float, float]] = []
    for i in range(num_segments):
        p1p = pl.getPoint3dAt(i)
        p2p = pl.getPoint3dAt((i + 1) % num_verts)
        p1 = (p1p.x, p1p.y)
        p2 = (p2p.x, p2p.y)
        points.append(p1)

        bulge = 0.0
        try:
            bulge = pl.getBulgeAt(i)
        except Exception:
            pass

        if abs(bulge) > 0.001:
            points.extend(_arc_points(p1, p2, bulge, max_step))
        else:
            points.extend(_linear_points(p1, p2, max_step))

    if not is_closed:
        last_p = pl.getPoint3dAt(num_verts - 1)
        points.append((last_p.x, last_p.y))
    return points


def _line_points(ent: Db.Entity, max_step: float) -> list[tuple[float, float]]:
    """Точки вдоль линии: start, промежуточные по шагу, end."""
    line = Db.Line.cast(ent)
    sp = line.startPoint()
    ep = line.endPoint()
    p1 = (sp.x, sp.y)
    p2 = (ep.x, ep.y)
    points = [p1]
    points.extend(_linear_points(p1, p2, max_step))
    points.append(p2)
    return points


@command(name="IGI_ELEV_MARK_LINES")
def mark_lines() -> None:
    """Отметки «СП_9.2» из ЦМР вдоль выбранных линий и полилиний с заданным шагом."""
    print("\n[IGI Tools] Запуск IGI_ELEV_MARK_LINES…")

    try:
        if not dem.is_loaded():
            print("[IGI Tools] ЦМР не загружена. Запустите IGI_DEM_TRACKER для подключения георастра.")
            return

        db = Db.curDb()
        block_id = ensure_block(db)
        if block_id is None:
            return

        reset_marks_stack()

        max_step = _show_step_dialog()
        if max_step is None:
            print("[IGI Tools] Команда отменена.")
            return

        # ── выбор объектов ──
        filter = [(Db.DxfCode.kDxfStart, "LINE,LWPOLYLINE")]
        impl_status, impl_ss = Ed.Editor.selectImplied()
        if impl_status == Ed.PromptStatus.eOk and impl_ss.size() > 0:
            oids = []
            for oid in impl_ss.toList():
                ent = Db.Entity(oid, Db.OpenMode.kForRead)
                try:
                    if ent.isDerivedFrom(Db.Line.desc()) or ent.isDerivedFrom(Db.Polyline.desc()):
                        oids.append(oid)
                finally:
                    ent.close()
            if not oids:
                print("[IGI Tools] Среди предварительно выбранных объектов нет линий или полилиний.")
                return
            print(f"[IGI Tools] Найдено предварительно выбранных объектов: {len(oids)}.")
        else:
            print("\nВыберите линии и полилинии...")
            res = Ed.Editor.select(filter)
            if res[0] != Ed.PromptStatus.eOk:
                print("[IGI Tools] Выбор отменён.")
                return
            ss = res[1]
            if ss.size() == 0:
                print("[IGI Tools] Объекты не найдены.")
                return
            oids = ss.toList()

        # ── расстановка отметок ──
        placed = 0
        skipped = 0
        for oid in oids:
            ent = Db.Entity(oid, Db.OpenMode.kForRead)
            try:
                if ent.isDerivedFrom(Db.Polyline.desc()):
                    pts = _polyline_points(ent, max_step)
                elif ent.isDerivedFrom(Db.Line.desc()):
                    pts = _line_points(ent, max_step)
                else:
                    continue
            except Exception as exc:
                print(f"[IGI Tools] Ошибка обработки объекта: {exc}")
                continue
            finally:
                ent.close()

            for x, y in pts:
                z = dem.get_elevation(x, y)
                if z is None:
                    skipped += 1
                    continue
                if not insert_mark(db, x, y, z):
                    print("[IGI Tools] Не удалось вставить блок «СП_9.2».")
                    continue
                placed += 1

        print(f"[IGI Tools] Нанесено отметок: {placed}, пропущено (нет данных ЦМР): {skipped}.")

    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")