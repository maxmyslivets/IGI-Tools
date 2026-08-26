"""Fill area: insert blocks/text/mtext inside a polyline boundary via CADPyRx."""

from __future__ import annotations

import json
import random
import traceback
from pathlib import Path

import wx

from pyrx import Ap, Db, Ge, Ed, command

# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------

_SETTINGS_PATH: Path | None = None


def _get_settings_path() -> Path:
    global _SETTINGS_PATH
    if _SETTINGS_PATH is None:
        from igi_tools.paths import get_resources_dir

        _SETTINGS_PATH = get_resources_dir() / "fill_area_settings.json"
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
# Helper: извлечь имя образца из ObjectId
# ---------------------------------------------------------------------------

def _get_sample_label(oid: Db.ObjectId) -> str:
    """Возвращает читаемое имя образца: имя блока или '[Текст]' / '[МТекст]'."""
    try:
        ent = Db.Entity(oid, Db.OpenMode.kForRead)
        if ent.isDerivedFrom(Db.BlockReference.desc()):
            bref = Db.BlockReference.cast(ent)
            btr_id = bref.blockTableRecord()
            btr = Db.BlockTableRecord(btr_id, Db.OpenMode.kForRead)
            name = btr.getName()
            btr.close()
            return name
        elif ent.isDerivedFrom(Db.Text.desc()):
            return "[Текст]"
        elif ent.isDerivedFrom(Db.MText.desc()):
            return "[МТекст]"
        return "[объект]"
    except Exception:
        return "[?]"


def _is_anonymous_block_def(oid: Db.ObjectId) -> bool:
    """Проверить, что ObjectId указывает на BlockReference от анонимного (динамического) блока."""
    try:
        ent = Db.Entity(oid, Db.OpenMode.kForRead)
        if ent.isDerivedFrom(Db.BlockReference.desc()):
            bref = Db.BlockReference.cast(ent)
            btr_id = bref.blockTableRecord()
            btr = Db.BlockTableRecord(btr_id, Db.OpenMode.kForRead)
            is_anon = btr.isAnonymous()
            btr.close()
            return is_anon
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class _ParamsDialog(wx.Dialog):
    """Модальный диалог параметров расстановки."""

    def __init__(
        self,
        boundary_selected: bool,
        sample_selected: bool,
        sample_name: str,
        saved_state: dict,
    ):
        wx.Dialog.__init__(
            self,
            None,
            title="IGI Fill Area — Параметры",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP,
        )
        self.SetMinSize(wx.Size(380, 400))

        self.result_data: dict | None = None

        # Состояния из saved_state
        bound_mode = saved_state.get("boundary_mode", 0)
        step_val = str(saved_state.get("step", 7.0))
        mode_idx = saved_state.get("mode_index", 0)

        panel = wx.Panel(self)
        vsizer = wx.BoxSizer(wx.VERTICAL)

        # ═══════════ Контур ═══════════
        bound_box = wx.StaticBox(panel, label="Контур")
        bsizer = wx.StaticBoxSizer(bound_box, wx.VERTICAL)

        # — Строка 1: Выбор контура —
        row1 = wx.BoxSizer(wx.HORIZONTAL)
        self.bound_radio_select = wx.RadioButton(
            bsizer.GetStaticBox(), label="Выбор контура", style=wx.RB_GROUP
        )
        self.bound_radio_select.SetValue(bound_mode == 0)
        self.bound_select_btn = wx.Button(bsizer.GetStaticBox(), label="Выбрать")
        self.bound_select_btn.Enable(bound_mode == 0)
        row1.Add(self.bound_radio_select, flag=wx.ALIGN_CENTER_VERTICAL)
        row1.Add((0, 0), proportion=1)
        row1.Add(self.bound_select_btn, flag=wx.ALIGN_CENTER_VERTICAL)
        bsizer.Add(row1, flag=wx.EXPAND | wx.BOTTOM, border=4)

        # — Строка 2: Определение контура —
        row2 = wx.BoxSizer(wx.HORIZONTAL)
        self.bound_radio_draw = wx.RadioButton(
            bsizer.GetStaticBox(), label="Определение контура"
        )
        self.bound_radio_draw.SetValue(bound_mode == 1)
        self.bound_draw_btn = wx.Button(bsizer.GetStaticBox(), label="Определить")
        self.bound_draw_btn.Enable(bound_mode == 1)
        row2.Add(self.bound_radio_draw, flag=wx.ALIGN_CENTER_VERTICAL)
        row2.Add((0, 0), proportion=1)
        row2.Add(self.bound_draw_btn, flag=wx.ALIGN_CENTER_VERTICAL)
        bsizer.Add(row2, flag=wx.EXPAND | wx.BOTTOM, border=4)

        # — Статус контура —
        self.bound_status = wx.StaticText(bsizer.GetStaticBox(), label="")
        bsizer.Add(self.bound_status, flag=wx.BOTTOM, border=2)

        if boundary_selected:
            self.bound_status.SetLabel("(+) Контур выбран")
            self.bound_status.SetForegroundColour(wx.Colour(0, 100, 0))
        else:
            self.bound_status.SetLabel("(-) Контур не выбран")
            self.bound_status.SetForegroundColour(wx.Colour(140, 140, 140))

        vsizer.Add(bsizer, flag=wx.EXPAND | wx.BOTTOM, border=12)

        # ═══════════ Образец ═══════════
        samp_box = wx.StaticBox(panel, label="Образец (блок / текстовый объект)")
        ssizer = wx.StaticBoxSizer(samp_box, wx.VERTICAL)

        # — Строка: Выбрать на чертеже —
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.samp_pick_btn = wx.Button(ssizer.GetStaticBox(), label="Выбрать на чертеже")
        row.Add(self.samp_pick_btn, flag=wx.ALIGN_CENTER_VERTICAL)
        ssizer.Add(row, flag=wx.EXPAND | wx.BOTTOM, border=4)

        # — Статус образца —
        self.samp_status = wx.StaticText(ssizer.GetStaticBox(), label="")
        ssizer.Add(self.samp_status, flag=wx.BOTTOM, border=2)

        if sample_selected and sample_name:
            self.samp_status.SetLabel(f"(+) {sample_name}")
            self.samp_status.SetForegroundColour(wx.Colour(0, 100, 0))
        else:
            self.samp_status.SetLabel("(-) Образец / блок не выбран")
            self.samp_status.SetForegroundColour(wx.Colour(140, 140, 140))

        vsizer.Add(ssizer, flag=wx.EXPAND | wx.BOTTOM, border=12)

        # ═══════════ Параметры расстановки ═══════════
        prm_box = wx.StaticBox(panel, label="Параметры расстановки")
        psizer = wx.StaticBoxSizer(prm_box, wx.VERTICAL)

        psizer.Add(
            wx.StaticText(psizer.GetStaticBox(), label="Интервал (шаг по X и Y):"),
            flag=wx.BOTTOM, border=4,
        )
        self.step_ctrl = wx.TextCtrl(psizer.GetStaticBox(), value=step_val)
        self.step_ctrl.SetSelection(-1, -1)
        if not saved_state:
            self.step_ctrl.SetFocus()
        psizer.Add(self.step_ctrl, flag=wx.EXPAND | wx.BOTTOM, border=12)

        psizer.Add(
            wx.StaticText(psizer.GetStaticBox(), label="Порядок расстановки:"),
            flag=wx.BOTTOM, border=4,
        )
        self.mode_radio = wx.RadioBox(
            psizer.GetStaticBox(),
            choices=_MODE_NAMES,
            style=wx.RA_SPECIFY_COLS,
        )
        self.mode_radio.SetSelection(min(mode_idx, 2))
        psizer.Add(self.mode_radio, flag=wx.EXPAND | wx.BOTTOM, border=8)

        # — Jitter (разброс) для случайного режима —
        self.jitter_label = wx.StaticText(psizer.GetStaticBox(), label="Разброс:")
        psizer.Add(self.jitter_label, flag=wx.BOTTOM, border=2)

        jitter_init = int(saved_state.get("jitter", 0.5) * 100)
        self.jitter_slider = wx.Slider(
            psizer.GetStaticBox(),
            value=jitter_init,
            minValue=0,
            maxValue=100,
            style=wx.SL_HORIZONTAL | wx.SL_LABELS,
        )
        psizer.Add(self.jitter_slider, flag=wx.EXPAND | wx.BOTTOM, border=4)

        # Разблокировать/заблокировать слайдер в зависимости от режима
        self._update_jitter_enabled(mode_idx == 2)

        vsizer.Add(psizer, flag=wx.EXPAND | wx.BOTTOM, border=16)

        # ═══ Кнопки ═══
        btns = wx.BoxSizer(wx.HORIZONTAL)
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Отмена")
        btns.Add(ok_btn, flag=wx.RIGHT, border=8)
        btns.Add(cancel_btn)
        vsizer.Add(btns, flag=wx.ALIGN_CENTER)

        # Отступ от краёв окна
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(vsizer, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        panel.SetSizerAndFit(outer)
        self.Fit()

        # События
        self.Bind(wx.EVT_RADIOBUTTON, self._on_bound_radio, self.bound_radio_select)
        self.Bind(wx.EVT_RADIOBUTTON, self._on_bound_radio, self.bound_radio_draw)

        self.Bind(wx.EVT_BUTTON, self._on_select_boundary, self.bound_select_btn)
        self.Bind(wx.EVT_BUTTON, self._on_draw_boundary, self.bound_draw_btn)
        self.Bind(wx.EVT_BUTTON, self._on_pick_sample, self.samp_pick_btn)

        self.Bind(wx.EVT_RADIOBOX, self._on_mode_change, self.mode_radio)

        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self._on_cancel, id=wx.ID_CANCEL)

        self.CenterOnScreen()

    # ── Текущее состояние UI ─────────────────────────────────

    def _get_ui_state(self) -> dict:
        return {
            "step": float(self.step_ctrl.GetValue().replace(",", ".")),
            "mode_index": self.mode_radio.GetSelection(),
            "boundary_mode": 0 if self.bound_radio_select.GetValue() else 1,
            "jitter": self.jitter_slider.GetValue() / 100.0,
        }

    # ── Радио контура ────────────────────────────────────────

    def _on_bound_radio(self, event):
        s = self.bound_radio_select.GetValue()
        self.bound_select_btn.Enable(s)
        self.bound_draw_btn.Enable(not s)

    # ── Переключатель режима (для блокировки слайдера) ────

    def _on_mode_change(self, event):
        self._update_jitter_enabled(self.mode_radio.GetSelection() == 2)

    def _update_jitter_enabled(self, enabled: bool) -> None:
        self.jitter_label.Enable(enabled)
        self.jitter_slider.Enable(enabled)

    # ── Валидация ────────────────────────────────────────────

    def _validate_step(self) -> bool:
        try:
            val = float(self.step_ctrl.GetValue().replace(",", "."))
            if val <= 0:
                raise ValueError
            self.step_ctrl.SetForegroundColour(wx.NullColour)
            self.step_ctrl.Refresh()
        except ValueError:
            self.step_ctrl.SetForegroundColour(wx.RED)
            self.step_ctrl.SetFocus()
            self.step_ctrl.Refresh()
            return False

        return True

    # ── Действия по кнопкам ──────────────────────────────────

    def _on_select_boundary(self, event):
        if not self._validate_step():
            return
        self.result_data = {"action": "select_boundary", **self._get_ui_state()}
        self.EndModal(wx.ID_OK)

    def _on_draw_boundary(self, event):
        if not self._validate_step():
            return
        self.result_data = {"action": "draw_boundary", **self._get_ui_state()}
        self.EndModal(wx.ID_OK)

    def _on_pick_sample(self, event):
        if not self._validate_step():
            return
        self.result_data = {"action": "pick_sample", **self._get_ui_state()}
        self.EndModal(wx.ID_OK)

    def _on_ok(self, event):
        if not self._validate_step():
            return

        self.result_data = {
            "action": "ok",
            **self._get_ui_state(),
        }
        self.EndModal(wx.ID_OK)

    def _on_cancel(self, event):
        self.result_data = None
        self.EndModal(wx.ID_CANCEL)


# ---------------------------------------------------------------------------
# Dialog helper
# ---------------------------------------------------------------------------

def _show_dialog(
    boundary_selected: bool,
    sample_selected: bool,
    sample_name: str,
    saved_state: dict,
) -> dict | None:
    """Показать wx-диалог через ShowModal. Возвращает dict параметров или None."""
    res_override = Ap.ResourceOverride()
    dlg = _ParamsDialog(
        boundary_selected,
        sample_selected,
        sample_name,
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
# Boundary helpers
# ---------------------------------------------------------------------------

def _draw_polyline_interactive() -> Db.ObjectId | None:
    """Интерактивное рисование замкнутой полилинии.

    Начиная со второй вершины AutoCAD рисует rubber-band от предыдущей точки.
    Возвращает ObjectId созданной полилинии или None.
    """
    print("\n[IGI Tools] Укажите вершины полилинии. Enter / ПКМ — завершить.")
    pts: list[Ge.Point3d] = []
    while True:
        n = len(pts) + 1
        if pts:
            base = pts[-1]
            res = Ed.Editor.getPoint(base, f"\n  Вершина {n}: ")
        else:
            res = Ed.Editor.getPoint(f"\n  Вершина {n}: ")

        if res[0] == Ed.PromptStatus.eOk:
            pts.append(res[1])
        elif res[0] in (Ed.PromptStatus.eNone, Ed.PromptStatus.eCancel):
            break
        else:
            break

    if len(pts) < 3:
        print("\n[IGI Tools] Нужно минимум 3 вершины для полилинии.")
        return None

    db = Db.curDb()
    pline = Db.Polyline()
    pline.setDatabaseDefaults(db)
    for i, p in enumerate(pts):
        pline.addVertexAt(i, Ge.Point2d(p.x, p.y))
    pline.setClosed(True)
    return db.addToModelspace(pline)


def _erase_entity(oid: Db.ObjectId) -> None:
    """Стереть объект из чертежа по ObjectId."""
    try:
        ent = Db.Entity(oid, Db.OpenMode.kForWrite)
        ent.erase(True)
        ent.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Sample extents helper
# ---------------------------------------------------------------------------

def _compute_half_extents(
    db: Db.Database,
    block_id: Db.ObjectId | None,
    sample_oid: Db.ObjectId | None,
    base_pt: Ge.Point3d | None,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> tuple[float, float]:
    """Вычислить полуширину и полувысоту bounding box образца для отступа от границы.

    Возвращает (half_x, half_y). Если вычислить не удалось — (0.0, 0.0).
    scale_x, scale_y применяются для блока из block table (восстановленного из конфига).
    """
    if block_id is not None:
        # Создаём временный BlockReference, добавляем в БД, получаем extents, удаляем
        tmp_bref = Db.BlockReference(Ge.Point3d(0, 0, 0), block_id)
        tmp_bref.setDatabaseDefaults(db)
        try:
            tmp_bref.setScaleFactors(Ge.Scale3d(scale_x, scale_y, 1.0))
        except Exception:
            pass
        tmp_id = db.addToModelspace(tmp_bref)
        try:
            ext = Db.Entity(tmp_id, Db.OpenMode.kForRead).getGeomExtents()
            hx = (ext.maxPoint().x - ext.minPoint().x) / 2.0
            hy = (ext.maxPoint().y - ext.minPoint().y) / 2.0
            return (hx, hy)
        except Exception:
            return (0.0, 0.0)
        finally:
            _erase_entity(tmp_id)
    elif sample_oid is not None and base_pt is not None:
        try:
            ent = Db.Entity(sample_oid, Db.OpenMode.kForRead)
            ext = ent.getGeomExtents()
            hx = max(abs(ext.maxPoint().x - base_pt.x), abs(base_pt.x - ext.minPoint().x))
            hy = max(abs(ext.maxPoint().y - base_pt.y), abs(base_pt.y - ext.minPoint().y))
            return (hx, hy)
        except Exception:
            return (0.0, 0.0)
    return (0.0, 0.0)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def point_in_poly(pt: Ge.Point3d, poly_pts: list[Ge.Point3d]) -> bool:
    """Проверка попадания точки в полигон (Ray-casting)."""
    x, y = pt.x, pt.y
    inside = False
    j = len(poly_pts) - 1
    for i in range(len(poly_pts)):
        xi, yi = poly_pts[i].x, poly_pts[i].y
        xj, yj = poly_pts[j].x, poly_pts[j].y

        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi)
        if intersect:
            inside = not inside
        j = i
    return inside


def get_curve_points(curve: Db.Curve, num_samples: int = 200) -> list[Ge.Point3d]:
    """Дискретизация кривой на точки для расчёта попадания внутрь."""
    pts: list[Ge.Point3d] = []
    try:
        end_param = curve.getEndParam()
        length = curve.getDistAtParam(end_param)

        for i in range(num_samples):
            dist = length * i / (num_samples - 1)
            pt = curve.getPointAtDist(dist)
            pts.append(pt)
    except Exception:
        print("\nОшибка при чтении геометрии контура.")
    return pts


# ---------------------------------------------------------------------------
# Сохраняемые ключи UI-состояния
# ---------------------------------------------------------------------------

_UI_KEYS = frozenset({"step", "mode_index", "boundary_mode", "jitter"})


# ---------------------------------------------------------------------------
# Main command
# ---------------------------------------------------------------------------

@command(name="IGI_FILL_AREA")
def fill_area() -> None:
    try:
        print("\n--- Расстановка блоков и текста в контуре ---")

        db = Db.curDb()

        # Загрузить сохранённые настройки
        saved_state = _load_settings()
        saved_state.setdefault("boundary_mode", 0)
        saved_state.setdefault("jitter", 0.7)

        # ObjectId в памяти
        boundary_oid: Db.ObjectId | None = None
        sample_oid: Db.ObjectId | None = None
        drawn_oid: Db.ObjectId | None = None

        # Если сохранён блок — попробовать восстановить его из block table
        saved_block_name = saved_state.get("saved_block_name", "")
        block_id_from_cfg: Db.ObjectId | None = None
        saved_block_scale_x = saved_state.get("saved_block_scale_x", 1.0)
        saved_block_scale_y = saved_state.get("saved_block_scale_y", 1.0)
        saved_block_layer = saved_state.get("saved_block_layer", "0")
        if saved_block_name:
            bt = Db.BlockTable(db.blockTableId(), Db.OpenMode.kForRead)
            if bt.has(saved_block_name):
                block_id_from_cfg = bt.getAt(saved_block_name)
                print(f"\n[IGI Tools] Восстановлен блок: {saved_block_name}")

        # Главный цикл
        while True:
            has_boundary = boundary_oid is not None
            has_sample = (sample_oid is not None) or (block_id_from_cfg is not None)
            sample_label = saved_block_name if block_id_from_cfg else (
                _get_sample_label(sample_oid) if sample_oid else ""
            )

            result = _show_dialog(
                has_boundary,
                has_sample,
                sample_label,
                saved_state,
            )
            if result is None:
                print("\n[IGI Tools] Отменено пользователем.")
                return

            action = result.get("action")

            # ── Выбор контура с чертежа ──
            if action == "select_boundary":
                saved_state.update({k: v for k, v in result.items() if k in _UI_KEYS})
                res_sel = Ed.Editor.entSel(
                    "\nВыберите границу заливки (Полилиния/Кривая/Сплайн): "
                )
                if res_sel[0] == Ed.PromptStatus.eOk:
                    boundary_oid = res_sel[1]
                    print("\n[IGI Tools] Контур выбран.")
                else:
                    print("\n[IGI Tools] Выбор контура отменён.")
                continue

            # ── Определение контура (рисование) ──
            if action == "draw_boundary":
                saved_state.update({k: v for k, v in result.items() if k in _UI_KEYS})
                drawn = _draw_polyline_interactive()
                if drawn is not None:
                    boundary_oid = drawn
                    drawn_oid = drawn
                    print("\n[IGI Tools] Контур нарисован.")
                else:
                    print("\n[IGI Tools] Определение контура отменено.")
                continue

            # ── Выбор образца с чертежа ──
            if action == "pick_sample":
                saved_state.update({k: v for k, v in result.items() if k in _UI_KEYS})

                res_pick = Ed.Editor.entSel(
                    "\nВыберите образец (Блок, Текст или МТекст): "
                )
                if res_pick[0] == Ed.PromptStatus.eOk:
                    picked_oid = res_pick[1]
                    # Определить имя и сохранить
                    label = _get_sample_label(picked_oid)
                    if label.startswith("["):
                        # Текст / МТекст — не сохраняем для автозагрузки
                        saved_state["saved_block_name"] = ""
                        block_id_from_cfg = None
                    elif _is_anonymous_block_def(picked_oid):
                        # Динамический блок — не запоминаем
                        saved_state["saved_block_name"] = ""
                        block_id_from_cfg = None
                        print("\n[IGI Tools] Динамический блок — не будет сохранён.")
                    else:
                        # Обычный блок — сохраняем имя, масштаб и слой
                        saved_state["saved_block_name"] = label
                        block_id_from_cfg = None
                        try:
                            bref = Db.BlockReference(picked_oid, Db.OpenMode.kForRead)
                            sf = bref.scaleFactors()
                            saved_state["saved_block_scale_x"] = sf.sx
                            saved_state["saved_block_scale_y"] = sf.sy
                            ln = bref.layer()
                            saved_state["saved_block_layer"] = ln
                        except Exception:
                            saved_state["saved_block_scale_x"] = 1.0
                            saved_state["saved_block_scale_y"] = 1.0
                            saved_state["saved_block_layer"] = "0"

                    sample_oid = picked_oid
                    print(f"\n[IGI Tools] Образец выбран: {label}")
                else:
                    print("\n[IGI Tools] Выбор образца отменён.")
                continue

            # ── OK ──
            if action == "ok":
                # Проверить контур
                if boundary_oid is None:
                    print("\n[IGI Tools] Не выбран контур. Выберите или нарисуйте контур.")
                    continue

                step = result["step"]
                mode_idx = result["mode_index"]
                mode_str = _MODE_NAMES[mode_idx]
                jitter = result.get("jitter", 0.7)

                # Сохранить в JSON
                save_data = {
                    "step": step,
                    "mode_index": mode_idx,
                    "boundary_mode": result.get("boundary_mode", 0),
                    "jitter": result.get("jitter", 0.7),
                }
                if block_id_from_cfg is not None:
                    save_data["saved_block_name"] = saved_block_name
                    save_data["saved_block_scale_x"] = saved_state.get("saved_block_scale_x", 1.0)
                    save_data["saved_block_scale_y"] = saved_state.get("saved_block_scale_y", 1.0)
                    save_data["saved_block_layer"] = saved_state.get("saved_block_layer", "0")
                elif sample_oid is not None:
                    label = _get_sample_label(sample_oid)
                    if not label.startswith("[") and not _is_anonymous_block_def(sample_oid):
                        save_data["saved_block_name"] = label
                        try:
                            bref = Db.BlockReference(sample_oid, Db.OpenMode.kForRead)
                            sf = bref.scaleFactors()
                            save_data["saved_block_scale_x"] = sf.sx
                            save_data["saved_block_scale_y"] = sf.sy
                            save_data["saved_block_layer"] = bref.layer()
                        except Exception:
                            save_data["saved_block_scale_x"] = 1.0
                            save_data["saved_block_scale_y"] = 1.0
                            save_data["saved_block_layer"] = "0"
                    else:
                        save_data["saved_block_name"] = ""
                else:
                    save_data["saved_block_name"] = ""
                _save_settings(save_data)

                # ── 3. Граница заливки ──
                curve = Db.Curve(boundary_oid, Db.OpenMode.kForRead)
                if not curve.isDerivedFrom(Db.Curve.desc()):
                    print("\n[IGI Tools] Контур не является кривой/полилинией!")
                    boundary_oid = None
                    continue

                # ── 4. Образец ──
                block_id_local: Db.ObjectId | None = None
                base_pt: Ge.Point3d | None = None

                if block_id_from_cfg is not None:
                    # Восстановленный блок — вставляем по определению
                    block_id_local = block_id_from_cfg
                    base_pt = Ge.Point3d(0, 0, 0)
                elif sample_oid is not None:
                    sample_ent = Db.Entity(sample_oid, Db.OpenMode.kForRead)
                    if sample_ent.isDerivedFrom(Db.BlockReference.desc()):
                        base_pt = Db.BlockReference.cast(sample_ent).position()
                    elif sample_ent.isDerivedFrom(Db.Text.desc()):
                        base_pt = Db.Text.cast(sample_ent).position()
                    elif sample_ent.isDerivedFrom(Db.MText.desc()):
                        base_pt = Db.MText.cast(sample_ent).location()
                    else:
                        print("\n[IGI Tools] Образец не поддерживается. Выберите Блок, Текст или МТекст.")
                        continue
                else:
                    # Запросить сейчас
                    res_pick = Ed.Editor.entSel(
                        "\nВыберите образец (Блок, Текст или МТекст): "
                    )
                    if res_pick[0] != Ed.PromptStatus.eOk:
                        print("\n[IGI Tools] Выбор образца отменён.")
                        continue
                    sample_oid = res_pick[1]
                    sample_ent = Db.Entity(sample_oid, Db.OpenMode.kForRead)
                    if sample_ent.isDerivedFrom(Db.BlockReference.desc()):
                        base_pt = Db.BlockReference.cast(sample_ent).position()
                    elif sample_ent.isDerivedFrom(Db.Text.desc()):
                        base_pt = Db.Text.cast(sample_ent).position()
                    elif sample_ent.isDerivedFrom(Db.MText.desc()):
                        base_pt = Db.MText.cast(sample_ent).location()
                    else:
                        print("\n[IGI Tools] Образец не поддерживается. Выберите Блок, Текст или МТекст.")
                        continue

                # ── 4b. Вычислить отступ от границы ──
                half_x, half_y = _compute_half_extents(db, block_id_local, sample_oid, base_pt, saved_block_scale_x, saved_block_scale_y)
                if half_x > 0 or half_y > 0:
                    print(f"\n[IGI Tools] Отступ от границы: X={half_x:.2f}, Y={half_y:.2f}")

                # ── 5. Геометрия контура ──
                poly_pts = get_curve_points(curve, 200)
                extents = curve.getGeomExtents()
                min_pt = extents.minPoint()
                max_pt = extents.maxPoint()
                curve.close()

                # ── 6. Расстановка ──
                dx = step
                dy = dx
                dy_step = dy / 2.0 if mode_str == "Шахматный" else dy

                count = 0
                y = min_pt.y
                row = 0

                while y <= max_pt.y:
                    x_offset = (dx / 2.0) if (mode_str == "Шахматный" and row % 2 != 0) else 0.0
                    x = min_pt.x + x_offset

                    while x <= max_pt.x:
                        insert_it = False

                        if mode_str in ("Сетка", "Шахматный"):
                            insert_pt = Ge.Point3d(x, y, 0.0)
                            # Проверка, что весь bounding box внутри контура
                            corners = [
                                Ge.Point3d(x - half_x, y - half_y, 0.0),
                                Ge.Point3d(x + half_x, y - half_y, 0.0),
                                Ge.Point3d(x - half_x, y + half_y, 0.0),
                                Ge.Point3d(x + half_x, y + half_y, 0.0),
                            ]
                            insert_it = all(point_in_poly(c, poly_pts) for c in corners)
                        elif mode_str == "Случайный":
                            rand_x = x + dx * 0.5 + (random.random() - 0.5) * dx * jitter
                            rand_y = y + dy * 0.5 + (random.random() - 0.5) * dy * jitter
                            insert_pt = Ge.Point3d(rand_x, rand_y, 0.0)
                            corners = [
                                Ge.Point3d(rand_x - half_x, rand_y - half_y, 0.0),
                                Ge.Point3d(rand_x + half_x, rand_y - half_y, 0.0),
                                Ge.Point3d(rand_x - half_x, rand_y + half_y, 0.0),
                                Ge.Point3d(rand_x + half_x, rand_y + half_y, 0.0),
                            ]
                            insert_it = all(point_in_poly(c, poly_pts) for c in corners)

                        if insert_it:
                            if block_id_local is not None:
                                bref = Db.BlockReference(insert_pt, block_id_local)
                                bref.setDatabaseDefaults(db)
                                # Применить сохранённый масштаб и слой
                                if block_id_local is block_id_from_cfg:
                                    try:
                                        bref.setScaleFactors(Ge.Scale3d(saved_block_scale_x, saved_block_scale_y, 1.0))
                                    except Exception:
                                        pass
                                    try:
                                        bref.setLayer(saved_block_layer)
                                    except Exception:
                                        pass
                                db.addToModelspace(bref)
                                count += 1
                            elif sample_oid is not None:
                                idmap = Db.IdMapping()
                                db.deepCloneObjects([sample_oid], db.currentSpaceId(), idmap)
                                clone_id = None
                                for pr in idmap.idPairs():
                                    if pr.isPrimary():
                                        clone_id = pr.value()
                                        break
                                if clone_id is not None:
                                    new_ent = Db.Entity(clone_id, Db.OpenMode.kForWrite)
                                    displacement = insert_pt - base_pt
                                    vec = Ge.Vector3d(displacement.x, displacement.y, 0.0)
                                    mat = Ge.Matrix3d.translation(vec)
                                    new_ent.transformBy(mat)
                                    count += 1

                        x += dx

                    y += dy_step
                    row += 1

                # ── 7. Удалить нарисованную полилинию ──
                if drawn_oid is not None:
                    _erase_entity(drawn_oid)
                    print("[IGI Tools] Нарисованный контур удалён.")

                print(f"\nГотово! Расставлено объектов: {count}")
                break

    except Exception as err:
        print("\nПроизошла ошибка в скрипте:")
        traceback.print_exc()


_MODE_NAMES = ["Шахматный", "Сетка", "Случайный"]