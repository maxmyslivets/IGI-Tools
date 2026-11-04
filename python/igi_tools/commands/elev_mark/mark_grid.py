"""Команда IGI_ELEV_MARK_GRID — отметки «СП_9.2» из ЦМР по сетке в границе."""

from __future__ import annotations

import math
import random
import traceback

from pyrx import Db, Ed, command

from igi_tools import dem
from igi_tools.commands.elev_mark.blocks import (
    ensure_block,
    insert_mark,
    reset_marks_stack,
)


# ---------------------------------------------------------------------------
# Шаг со случайной ошибкой
# ---------------------------------------------------------------------------


def _step_error(step: float, dec_percent: float, inc_percent: float) -> float:
    """Случайный шаг в [step*(1-dec/100), step*(1+inc/100)]."""
    lo = step * (1.0 - dec_percent / 100.0)
    hi = step * (1.0 + inc_percent / 100.0)
    return random.uniform(lo, hi)


# ---------------------------------------------------------------------------
# wx-диалог параметров
# ---------------------------------------------------------------------------


def _show_grid_dialog() -> dict | None:
    """Модальный диалог с параметрами сетки. Возвращает dict | None."""
    import wx

    class _GridDialog(wx.Dialog):
        def __init__(self):
            wx.Dialog.__init__(
                self,
                None,
                title="Отметки по сетке — Параметры",
                style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
            )
            self.SetMinSize(wx.Size(380, 300))

            panel = wx.Panel(self)
            vsizer = wx.BoxSizer(wx.VERTICAL)

            # Шаг сетки
            vsizer.Add(
                wx.StaticText(panel, label="Шаг сетки (м):"),
                flag=wx.BOTTOM,
                border=4,
            )
            self.step_ctrl = wx.TextCtrl(panel, value="20.0")
            vsizer.Add(self.step_ctrl, flag=wx.EXPAND | wx.BOTTOM, border=12)

            # Учесть направление
            self.align_chk = wx.CheckBox(panel, label="Учесть направление")
            vsizer.Add(self.align_chk, flag=wx.BOTTOM, border=8)

            # Имитировать неравномерный шаг
            self.random_chk = wx.CheckBox(
                panel, label="Имитировать неравномерный шаг"
            )
            vsizer.Add(self.random_chk, flag=wx.BOTTOM, border=4)

            # Уменьшение, %
            vsizer.Add(
                wx.StaticText(panel, label="Уменьшение, %:"),
                flag=wx.BOTTOM,
                border=2,
            )
            self.dec_ctrl = wx.TextCtrl(panel, value="15.0")
            self.dec_ctrl.Enable(False)
            vsizer.Add(self.dec_ctrl, flag=wx.EXPAND | wx.BOTTOM, border=8)

            # Увеличение, %
            vsizer.Add(
                wx.StaticText(panel, label="Увеличение, %:"),
                flag=wx.BOTTOM,
                border=2,
            )
            self.inc_ctrl = wx.TextCtrl(panel, value="5.0")
            self.inc_ctrl.Enable(False)
            vsizer.Add(self.inc_ctrl, flag=wx.EXPAND | wx.BOTTOM, border=12)

            # Привязка блокировки полей к чекбоксу неравномерного шага
            self.random_chk.Bind(wx.EVT_CHECKBOX, self._on_random_toggle)

            # Кнопки
            btn_row = wx.BoxSizer(wx.HORIZONTAL)
            ok_btn = wx.Button(panel, wx.ID_OK, label="Выполнить")
            cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="Отмена")
            btn_row.Add(ok_btn, flag=wx.RIGHT, border=8)
            btn_row.Add(cancel_btn)
            vsizer.Add(btn_row, flag=wx.ALIGN_CENTER)

            panel.SetSizer(vsizer)
            vsizer.Fit(panel)
            self.Fit()
            self.CenterOnScreen()

        def _on_random_toggle(self, _event):
            enabled = self.random_chk.IsChecked()
            self.dec_ctrl.Enable(enabled)
            self.inc_ctrl.Enable(enabled)

        def get_data(self) -> dict:
            try:
                step = float(self.step_ctrl.GetValue().replace(",", "."))
            except ValueError:
                step = 20.0
            if step <= 0:
                step = 20.0
            return {
                "step": step,
                "use_direction": self.align_chk.IsChecked(),
                "use_random": self.random_chk.IsChecked(),
                "decrease_pct": float(self.dec_ctrl.GetValue().replace(",", ".")),
                "increase_pct": float(self.inc_ctrl.GetValue().replace(",", ".")),
            }

    dlg = _GridDialog()
    if dlg.ShowModal() == wx.ID_OK:
        data = dlg.get_data()
        dlg.Destroy()
        return data
    dlg.Destroy()
    return None


# ---------------------------------------------------------------------------
# Угол по отрезку/полилинии
# ---------------------------------------------------------------------------


def _get_entity_angle(oid: Db.ObjectId) -> float:
    """Угол наклона отрезка/полилинии через первые две точки."""
    ent = Db.Entity(oid, Db.OpenMode.kForRead)
    try:
        if ent.isDerivedFrom(Db.Line.desc()):
            line = Db.Line.cast(ent)
            sp = line.startPoint()
            ep = line.endPoint()
            return math.atan2(ep.y - sp.y, ep.x - sp.x)
        elif ent.isDerivedFrom(Db.Polyline.desc()):
            pl = Db.Polyline.cast(ent)
            if pl.numVerts() >= 2:
                p0 = pl.getPoint3dAt(0)
                p1 = pl.getPoint3dAt(1)
                return math.atan2(p1.y - p0.y, p1.x - p0.x)
        return 0.0
    finally:
        ent.close()


# ---------------------------------------------------------------------------
# Точки дугового сегмента (bulge)
# ---------------------------------------------------------------------------


def _arc_points(
    p1: tuple[float, float],
    p2: tuple[float, float],
    bulge: float,
    max_step: float,
) -> list[tuple[float, float]]:
    """Промежуточные точки дуги сегмента (p1 и p2 не входят)."""
    points: list[tuple[float, float]] = []
    x1, y1 = p1
    x2, y2 = p2

    chord = math.hypot(x2 - x1, y2 - y1)
    if chord < 0.001:
        return points

    alpha = 4 * math.atan(abs(bulge))
    sin_half = math.sin(alpha / 2)
    if sin_half < 1e-9:
        return points
    radius = chord / (2 * sin_half)
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
    num_divisions = max(2, math.ceil(arc_len / max_step))

    for j in range(1, num_divisions):
        t = j / num_divisions
        curr_angle = start_angle + angle_diff * t
        points.append(
            (
                cx + radius * math.cos(curr_angle),
                cy + radius * math.sin(curr_angle),
            )
        )

    return points


# ---------------------------------------------------------------------------
# Команда
# ---------------------------------------------------------------------------


@command(name="IGI_ELEV_MARK_GRID")
def mark_grid() -> None:
    """Отметки «СП_9.2» из ЦМР по сетке в границе."""
    print("\n[IGI Tools] Запуск IGI_ELEV_MARK_GRID…")

    try:
        # ── 1. Проверки ──
        if not dem.is_loaded():
            print(
                "[IGI Tools] ЦМР не загружена. "
                "Запустите IGI_DEM_MANAGER для подключения георастра."
            )
            return

        db = Db.curDb()
        block_id = ensure_block(db)
        if block_id is None:
            return

        reset_marks_stack()

        # ── 2. Диалог параметров ──
        params = _show_grid_dialog()
        if params is None:
            print("[IGI Tools] Команда отменена.")
            return

        step = params["step"]
        use_direction = params["use_direction"]
        use_random = params["use_random"]
        dec_pct = params["decrease_pct"]
        inc_pct = params["increase_pct"]

        # ── 3. Выбор границы ──
        res = Ed.Editor.entSel("\nВыберите замкнутую полилинию-границу: ")
        if res[0] != Ed.PromptStatus.eOk:
            print("[IGI Tools] Выбор отменён.")
            return

        oid = res[1]
        ent = Db.Entity(oid, Db.OpenMode.kForRead)
        try:
            if not ent.isDerivedFrom(Db.Polyline.desc()):
                print("[IGI Tools] Граница должна быть замкнутой полилинией.")
                return
            pl = Db.Polyline.cast(ent)
            if not pl.isClosed():
                print("[IGI Tools] Граница должна быть замкнутой полилинией.")
                return

            n = pl.numVerts()
            vertices = [
                (pl.getPoint3dAt(i).x, pl.getPoint3dAt(i).y) for i in range(n)
            ]
            if len(vertices) < 3:
                print("[IGI Tools] Граница должна быть замкнутой полилинией.")
                return

            poly_points: list[tuple[float, float]] = []
            for i in range(n):
                p1 = vertices[i]
                p2 = vertices[(i + 1) % n]
                poly_points.append(p1)
                bulge = pl.getBulgeAt(i)
                if abs(bulge) > 0.001:
                    # Промежуточные точки дуги (без p1 и p2)
                    poly_points.extend(_arc_points(p1, p2, bulge, step))
        finally:
            ent.close()

        # ── 4. Направление ──
        angle = 0.0
        if use_direction:
            res2 = Ed.Editor.entSel(
                "\nВыберите отрезок или полилинию для ориентации сетки: "
            )
            if res2[0] == Ed.PromptStatus.eOk:
                angle = _get_entity_angle(res2[1])
                print(f"[IGI Tools] Угол ориентации сетки: {math.degrees(angle):.2f}°")
            else:
                print("[IGI Tools] Ориентация не выбрана, угол = 0°.")

        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # ── 5. Генерация сетки ──
        from shapely.geometry import Point, Polygon

        polygon = Polygon(poly_points)

        min_x, min_y, max_x, max_y = polygon.bounds
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        diag = math.hypot(max_x - min_x, max_y - min_y)

        max_steps = int(diag / step) + 2
        rows = 2 * max_steps + 1
        cols = 2 * max_steps + 1
        centre = max_steps

        # row_u[i][j] — продольное смещение для строки i, столбца j
        row_u: list[list[float]] = []
        for _ in range(rows):
            seq = [0.0] * cols
            for j in range(centre + 1, cols):
                d = _step_error(step, dec_pct, inc_pct) if use_random else step
                seq[j] = seq[j - 1] + d
            for j in range(centre - 1, -1, -1):
                d = _step_error(step, dec_pct, inc_pct) if use_random else step
                seq[j] = seq[j + 1] - d
            row_u.append(seq)

        # col_v[j][i] — поперечное смещение для столбца j, строки i
        col_v: list[list[float]] = []
        for _ in range(cols):
            seq = [0.0] * rows
            for i in range(centre + 1, rows):
                d = _step_error(step, dec_pct, inc_pct) if use_random else step
                seq[i] = seq[i - 1] + d
            for i in range(centre - 1, -1, -1):
                d = _step_error(step, dec_pct, inc_pct) if use_random else step
                seq[i] = seq[i + 1] - d
            col_v.append(seq)

        offset = max_steps
        points_created = 0
        points_skipped = 0

        for i_glob in range(-max_steps, max_steps + 1):
            i_loc = i_glob + offset
            for j_glob in range(-max_steps, max_steps + 1):
                j_loc = j_glob + offset

                u = row_u[i_loc][j_loc]
                v = col_v[j_loc][i_loc]

                x = center_x + u * cos_a - v * sin_a
                y = center_y + u * sin_a + v * cos_a

                if polygon.contains(Point(x, y)):
                    z = dem.get_elevation(x, y)
                    if z is None:
                        points_skipped += 1
                        continue
                    if insert_mark(db, x, y, z):
                        points_created += 1
                    else:
                        points_skipped += 1

        print(
            f"[IGI Tools] Нанесено отметок: {points_created}, "
            f"пропущено: {points_skipped}."
        )

    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")