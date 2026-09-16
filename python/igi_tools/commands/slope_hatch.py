"""Slope hatch: draw hatch lines between two curves (brink and toe)."""

from __future__ import annotations

import json
import math
import traceback
from pathlib import Path

import wx

from pyrx import Ap, Db, Ge, Ed, command

# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------

_DEFAULT_LAYER_NAME = "17 Рельеф"
_DEFAULT_STEP = 0.5
_SETTINGS_PATH: Path | None = None

_MODE_NAMES = ("Только длинные", "Чередование")

# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------


def _get_settings_path() -> Path:
    global _SETTINGS_PATH
    if _SETTINGS_PATH is None:
        from igi_tools.paths import get_resources_dir

        _SETTINGS_PATH = get_resources_dir() / "slope_hatch_settings.json"
    return _SETTINGS_PATH


def _load_settings() -> dict:
    try:
        with open(_get_settings_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_settings(data: dict) -> None:
    try:
        path = _get_settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # non-critical


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
# Entity → coordinate extraction (new engine using Db.Curve API)
# ---------------------------------------------------------------------------


def _sample_curve(curve: Db.Curve, step: float) -> tuple[list[Ge.Point3d], float]:
    """Sample points at equal arc-length intervals along a Curve (handles arcs natively).
    Returns (points_xy, total_length). Points have Z=0."""
    end_param = curve.getEndParam()
    total = curve.getDistAtParam(end_param)
    if total < 1e-12:
        return [], 0.0
    n = max(1, int(total / step))
    pts = []
    for i in range(n + 1):
        d = total * i / n
        raw = curve.getPointAtDist(d)
        pts.append(Ge.Point3d(raw.x, raw.y, 0.0))
    return pts, total


def _tessellate_curve(curve: Db.Curve, num_segments: int = 300) -> list[Ge.Point3d]:
    """Tessellate curve into many small points for segment-based intersection/projection."""
    try:
        end_param = curve.getEndParam()
        total = curve.getDistAtParam(end_param)
        if total < 1e-12:
            return []
        pts = []
        for i in range(num_segments + 1):
            d = total * i / num_segments
            raw = curve.getPointAtDist(d)
            pts.append(Ge.Point3d(raw.x, raw.y, 0.0))
        return pts
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Geometry helpers (2D)
# ---------------------------------------------------------------------------


def _tangent_at(pts: list[Ge.Point3d], idx: int) -> Ge.Vector3d:
    """Approximate tangent (unit) at sample index using neighbours."""
    n = len(pts)
    if n == 1:
        return Ge.Vector3d(1, 0, 0)
    if idx == 0:
        dx = pts[1].x - pts[0].x
        dy = pts[1].y - pts[0].y
    elif idx == n - 1:
        dx = pts[-1].x - pts[-2].x
        dy = pts[-1].y - pts[-2].y
    else:
        dx = pts[idx + 1].x - pts[idx - 1].x
        dy = pts[idx + 1].y - pts[idx - 1].y
    length = math.hypot(dx, dy)
    if length < 1e-12:
        return Ge.Vector3d(1, 0, 0)
    return Ge.Vector3d(dx / length, dy / length, 0.0)


def _normal(tan: Ge.Vector3d) -> Ge.Vector3d:
    """Left-pointing normal (rotate tangent 90° CCW in XY)."""
    return Ge.Vector3d(-tan.y, tan.x, 0.0)


def _segment_ray_intersection(
    origin: Ge.Point3d,
    direction: Ge.Vector3d,
    a: Ge.Point3d,
    b: Ge.Point3d,
) -> Ge.Point3d | None:
    """Intersect a ray (origin + t*direction) with segment a-b. Return point or None."""
    dx = b.x - a.x
    dy = b.y - a.y
    denom = direction.x * dy - direction.y * dx
    if abs(denom) < 1e-12:
        return None  # parallel
    t = ((a.x - origin.x) * dy - (a.y - origin.y) * dx) / denom
    u = ((a.x - origin.x) * direction.y - (a.y - origin.y) * direction.x) / denom
    if t < 0.0:
        return None  # behind ray
    if u < 0.0 or u > 1.0:
        return None  # outside segment
    return Ge.Point3d(
        origin.x + t * direction.x,
        origin.y + t * direction.y,
        0.0,
    )


def _project_point_on_segment(
    pt: Ge.Point3d,
    a: Ge.Point3d,
    b: Ge.Point3d,
) -> tuple[Ge.Point3d, float]:
    """Project point onto segment a-b. Return (closest_point, distance)."""
    dx = b.x - a.x
    dy = b.y - a.y
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-12:
        closest = a
    else:
        t = ((pt.x - a.x) * dx + (pt.y - a.y) * dy) / seg_len_sq
        t = max(0.0, min(1.0, t))
        closest = Ge.Point3d(a.x + t * dx, a.y + t * dy, 0.0)
    dist = math.hypot(pt.x - closest.x, pt.y - closest.y)
    return (closest, dist)


def _arc_length_along(toe_pts: list[Ge.Point3d], pt: Ge.Point3d) -> float:
    """Estimate arc-length position of a point along a tessellated polyline."""
    best = float('inf')
    best_i = 0
    for i in range(len(toe_pts) - 1):
        a, b = toe_pts[i], toe_pts[i + 1]
        dx = b.x - a.x
        dy = b.y - a.y
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq < 1e-12:
            continue
        t = ((pt.x - a.x) * dx + (pt.y - a.y) * dy) / seg_len_sq
        if t < 0.0 or t > 1.0:
            continue
        proj_x = a.x + t * dx
        proj_y = a.y + t * dy
        d = math.hypot(pt.x - proj_x, pt.y - proj_y)
        if d < best:
            best = d
            best_i = i
    cum = 0.0
    for i in range(best_i):
        dx = toe_pts[i + 1].x - toe_pts[i].x
        dy = toe_pts[i + 1].y - toe_pts[i].y
        cum += math.hypot(dx, dy)
    a, b = toe_pts[best_i], toe_pts[best_i + 1]
    dx = b.x - a.x
    dy = b.y - a.y
    seg_len = math.hypot(dx, dy)
    if seg_len > 1e-12:
        t = ((pt.x - a.x) * dx + (pt.y - a.y) * dy) / (seg_len * seg_len)
        t = max(0.0, min(1.0, t))
        cum += seg_len * t
    return cum


def _find_brink_normal_dir(brink_pt: Ge.Point3d, toe_curve: Db.Curve, tan: Ge.Vector3d) -> Ge.Vector3d:
    """Determine which normal direction (left or right) points toward the toe.
    Use getClosestPointTo to find nearest toe point, then check dot product with both normals.
    Return the normal whose dot with direction-to-toe is positive."""
    nrm_left = _normal(tan)
    nrm_right = Ge.Vector3d(-nrm_left.x, -nrm_left.y, 0.0)
    try:
        closest = toe_curve.getClosestPointTo(brink_pt, False)
        to_toe = Ge.Vector3d(closest.x - brink_pt.x, closest.y - brink_pt.y, 0.0)
        to_len = to_toe.length()
        if to_len < 1e-12:
            return nrm_left
        to_toe = to_toe / to_len
        if nrm_left.dotProduct(to_toe) > 0:
            return nrm_left
        else:
            return nrm_right
    except Exception:
        return nrm_left


def _find_toe_point(
    brink_pt: Ge.Point3d,
    normal_dir: Ge.Vector3d,
    toe_pts: list[Ge.Point3d],
    toe_curve: Db.Curve,
    prev_toe_pt: Ge.Point3d | None,
) -> Ge.Point3d | None:
    """Find hatch-line end point on toe.
    1. Try ray intersection with tessellated toe segments along normal_dir (forward only, t>0).
    2. If no intersection, fall back to getClosestPointTo.
    3. ANTI-CROSSING: compute arc-length position of toe_pt along toe_curve via
       getParamAtPoint + getDistAtParam. If position < prev_position, fall back
       to getClosestPointTo (clamp)."""
    if len(toe_pts) < 2:
        return None

    # Step 1: ray intersection along normal_dir (forward only)
    best_pt: Ge.Point3d | None = None
    best_dist = float("inf")
    for i in range(len(toe_pts) - 1):
        a, b = toe_pts[i], toe_pts[i + 1]
        pt = _segment_ray_intersection(brink_pt, normal_dir, a, b)
        if pt is not None:
            d = math.hypot(pt.x - brink_pt.x, pt.y - brink_pt.y)
            if d < best_dist:
                best_dist = d
                best_pt = pt

    ray_hit = best_pt is not None

    # Step 2: fallback to closest point on toe curve
    if best_pt is None:
        try:
            raw = toe_curve.getClosestPointTo(brink_pt, False)
            best_pt = Ge.Point3d(raw.x, raw.y, 0.0)
        except Exception:
            return None

    if best_pt is None:
        return None

    # Step 3: ANTI-CROSSING — only when both ray-hit succeeded and prev point exists
    if prev_toe_pt is not None and ray_hit:
        try:
            pos = toe_curve.getDistAtParam(toe_curve.getParamAtPoint(best_pt))
            prev_pos = toe_curve.getDistAtParam(
                toe_curve.getParamAtPoint(prev_toe_pt)
            )
            if pos < prev_pos:
                # Clamp: project current brink directly onto toe curve
                raw = toe_curve.getClosestPointTo(brink_pt, False)
                best_pt = Ge.Point3d(raw.x, raw.y, 0.0)
        except Exception:
            pass

    return best_pt


# ---------------------------------------------------------------------------
# wx dialog
# ---------------------------------------------------------------------------

class _ParamsDialog(wx.Dialog):
    """Modal dialog for slope hatch parameters."""

    def __init__(
        self,
        brink_selected: bool,
        toe_selected: bool,
        saved_state: dict,
    ):
        wx.Dialog.__init__(
            self,
            None,
            title="IGI Slope Hatch — Параметры",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
        )
        self.SetMinSize(wx.Size(400, 450))

        self.result_data: dict | None = None

        step_val = str(saved_state.get("step", _DEFAULT_STEP))
        mode_idx = saved_state.get("mode_index", 0)
        layer_mode = saved_state.get("layer_mode", 0)
        custom_layer = saved_state.get("custom_layer", _DEFAULT_LAYER_NAME)

        panel = wx.Panel(self)
        vsizer = wx.BoxSizer(wx.VERTICAL)

        # ═══════════ Объекты ═══════════
        obj_box = wx.StaticBox(panel, label="Объекты")
        osizer = wx.StaticBoxSizer(obj_box, wx.VERTICAL)

        self.brink_status = wx.StaticText(osizer.GetStaticBox(), label="")
        osizer.Add(self.brink_status, flag=wx.BOTTOM, border=4)
        self.toe_status = wx.StaticText(osizer.GetStaticBox(), label="")
        osizer.Add(self.toe_status, flag=wx.BOTTOM, border=2)

        self._update_object_status(brink_selected, toe_selected)

        vsizer.Add(osizer, flag=wx.EXPAND | wx.BOTTOM, border=12)

        # ═══════════ Параметры штриховки ═══════════
        prm_box = wx.StaticBox(panel, label="Параметры штриховки")
        psizer = wx.StaticBoxSizer(prm_box, wx.VERTICAL)

        psizer.Add(
            wx.StaticText(psizer.GetStaticBox(), label="Шаг (ед. чертежа):"),
            flag=wx.BOTTOM, border=4,
        )
        self.step_ctrl = wx.TextCtrl(psizer.GetStaticBox(), value=step_val)
        self.step_ctrl.SetSelection(-1, -1)
        if not saved_state:
            self.step_ctrl.SetFocus()
        psizer.Add(self.step_ctrl, flag=wx.EXPAND | wx.BOTTOM, border=8)

        psizer.Add(
            wx.StaticText(psizer.GetStaticBox(), label="Режим:"),
            flag=wx.BOTTOM, border=4,
        )
        self.mode_radio = wx.RadioBox(
            psizer.GetStaticBox(),
            choices=_MODE_NAMES,
            style=wx.RA_SPECIFY_COLS,
        )
        self.mode_radio.SetSelection(min(mode_idx, 1))
        psizer.Add(self.mode_radio, flag=wx.EXPAND | wx.BOTTOM, border=4)

        vsizer.Add(psizer, flag=wx.EXPAND | wx.BOTTOM, border=12)

        # ═══════════ Слой ═══════════
        layer_box = wx.StaticBox(panel, label="Слой для штриховки")
        lsizer = wx.StaticBoxSizer(layer_box, wx.VERTICAL)

        self.layer_radio_std = wx.RadioButton(
            lsizer.GetStaticBox(), label=f"Использовать стандартный слой «{_DEFAULT_LAYER_NAME}»",
            style=wx.RB_GROUP,
        )
        self.layer_radio_std.SetValue(layer_mode == 0)
        lsizer.Add(self.layer_radio_std, flag=wx.BOTTOM, border=4)

        self.layer_radio_pick = wx.RadioButton(
            lsizer.GetStaticBox(), label="Выбрать другой",
        )
        self.layer_radio_pick.SetValue(layer_mode == 1)
        row_layer_btn = wx.BoxSizer(wx.HORIZONTAL)
        self.layer_pick_btn = wx.Button(
            lsizer.GetStaticBox(), label="Выбрать из чертежа"
        )
        self.layer_pick_btn.Enable(layer_mode == 1)
        row_layer_btn.Add((16, 0))
        row_layer_btn.Add(self.layer_pick_btn)
        lsizer.Add(self.layer_radio_pick, flag=wx.BOTTOM, border=2)
        lsizer.Add(row_layer_btn, flag=wx.BOTTOM, border=4)

        # ── Результат выбора слоя (обновляется после pick_layer) ──
        self.layer_pick_result = wx.StaticText(lsizer.GetStaticBox(), label="")
        lsizer.Add(self.layer_pick_result, flag=wx.BOTTOM, border=4)

        row_create = wx.BoxSizer(wx.HORIZONTAL)
        self.layer_radio_create = wx.RadioButton(
            lsizer.GetStaticBox(), label="Создать",
        )
        self.layer_radio_create.SetValue(layer_mode == 2)
        self.layer_create_ctrl = wx.TextCtrl(
            lsizer.GetStaticBox(), value=custom_layer if layer_mode == 2 else "",
        )
        self.layer_create_ctrl.Enable(layer_mode == 2)
        row_create.Add(self.layer_radio_create, flag=wx.ALIGN_CENTER_VERTICAL)
        row_create.Add((4, 0))
        row_create.Add(self.layer_create_ctrl, proportion=1,
                       flag=wx.ALIGN_CENTER_VERTICAL)
        lsizer.Add(row_create, flag=wx.EXPAND | wx.BOTTOM, border=2)

        vsizer.Add(lsizer, flag=wx.EXPAND | wx.BOTTOM, border=16)

        # ═══ Кнопки ═══
        btns = wx.BoxSizer(wx.HORIZONTAL)
        ok_btn = wx.Button(panel, wx.ID_OK, "Построить")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        btns.Add(ok_btn, flag=wx.RIGHT, border=8)
        btns.Add(cancel_btn)
        vsizer.Add(btns, flag=wx.ALIGN_CENTER)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(vsizer, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        panel.SetSizerAndFit(outer)
        self.Fit()

        # Events
        self.Bind(wx.EVT_RADIOBUTTON, self._on_layer_radio, self.layer_radio_std)
        self.Bind(wx.EVT_RADIOBUTTON, self._on_layer_radio, self.layer_radio_pick)
        self.Bind(wx.EVT_RADIOBUTTON, self._on_layer_radio, self.layer_radio_create)
        self.Bind(wx.EVT_BUTTON, self._on_pick_layer, self.layer_pick_btn)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self._on_cancel, id=wx.ID_CANCEL)

        self.CenterOnScreen()

    # ── UI update helpers ─────────────────────────────────

    def _update_object_status(self, brink_selected: bool, toe_selected: bool) -> None:
        if brink_selected:
            self.brink_status.SetLabel("(+) Бровка выбрана")
            self.brink_status.SetForegroundColour(wx.Colour(0, 100, 0))
        else:
            self.brink_status.SetLabel("(-) Бровка не выбрана")
            self.brink_status.SetForegroundColour(wx.Colour(140, 140, 140))

        if toe_selected:
            self.toe_status.SetLabel("(+) Подошва выбрана")
            self.toe_status.SetForegroundColour(wx.Colour(0, 100, 0))
        else:
            self.toe_status.SetLabel("(-) Подошва не выбрана")
            self.toe_status.SetForegroundColour(wx.Colour(140, 140, 140))

    def _get_layer_mode(self) -> int:
        if self.layer_radio_std.GetValue():
            return 0
        elif self.layer_radio_pick.GetValue():
            return 1
        else:
            return 2

    # ── Events ────────────────────────────────────────────

    def _on_layer_radio(self, evt) -> None:
        mode = self._get_layer_mode()
        self.layer_pick_btn.Enable(mode == 1)
        self.layer_create_ctrl.Enable(mode == 2)

    def _on_pick_layer(self, evt) -> None:
        self.result_data = {"action": "pick_layer"}
        self.EndModal(wx.ID_OK)

    def _on_ok(self, evt) -> None:
        try:
            step = float(self.step_ctrl.GetValue().replace(",", "."))
            if step <= 0:
                raise ValueError
        except (ValueError, AttributeError):
            wx.MessageBox(
                "Шаг должен быть положительным числом.",
                "Ошибка",
                wx.OK | wx.ICON_ERROR,
            )
            return
        self.result_data = {
            "action": "ok",
            "step": step,
            "mode_index": self.mode_radio.GetSelection(),
            "layer_mode": self._get_layer_mode(),
            "custom_layer": self.layer_create_ctrl.GetValue().strip(),
        }
        evt.Skip()

    def _on_cancel(self, evt) -> None:
        self.result_data = None
        evt.Skip()


def _show_dialog(
    brink_selected: bool,
    toe_selected: bool,
    saved_state: dict,
) -> dict | None:
    """Show wx dialog. Returns dict or None."""
    res_override = Ap.ResourceOverride()
    dlg = _ParamsDialog(
        brink_selected,
        toe_selected,
        saved_state,
    )
    try:
        if dlg.ShowModal() == wx.ID_OK:
            return dlg.result_data
        return None
    except Exception as e:
        print(f"\nОшибка UI: {e}\n")
        return None
    finally:
        dlg.Destroy()
        del res_override


# ---------------------------------------------------------------------------
# Segment properties
# ---------------------------------------------------------------------------


def _apply_segment_props(line: Db.Line, db: Db.Database) -> None:
    """Apply user-specified properties to the segment."""
    # Colour — ByBlock (ACI 0)
    line.setColorIndex(0)
    # Linetype — ByLayer
    line.setLinetype(db.byLayerLinetype())
    # Linetype scale
    line.setLinetypeScale(0.5)
    # Line weight — 0.15 mm
    line.setLineWeight(Db.LineWeight.kLnWt015)


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

            # action == "ok" — выйти из диалога
            step = result["step"]
            mode_idx = result["mode_index"]

            layer_mode = result.get("layer_mode", 0)
            if layer_mode == 0:
                layer_name = _DEFAULT_LAYER_NAME
            elif layer_mode == 1:
                layer_name = picked_layer_name or _DEFAULT_LAYER_NAME
            else:
                layer_name = result.get("custom_layer", "") or _DEFAULT_LAYER_NAME

            print(f"\n[IGI Tools] Шаг: {step}, режим: {_MODE_NAMES[mode_idx]}, слой: {layer_name}")
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

        # Sample brink at equal arc-length intervals (handles arcs natively)
        sample_pts, total_len = _sample_curve(brink_curve, step)
        if len(sample_pts) < 2:
            print("\n[IGI Tools] Бровка слишком коротка.")
            return

        # Tessellate toe for segment intersection/projection
        toe_pts = _tessellate_curve(toe_curve, 300)
        if len(toe_pts) < 2:
            print("\n[IGI Tools] Подошва содержит менее 2 точек.")
            return

        layer_id = _ensure_layer(db, layer_name)

        count = 0
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
