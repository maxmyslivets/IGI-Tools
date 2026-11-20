"""Slope wx dialog for parameters."""

from __future__ import annotations

import wx
from pyrx import Ap, Db

from igi_tools.commands.slope.config import (
    _DEFAULT_BOTTOM_OFFSET,
    _DEFAULT_LAYER,
    _DEFAULT_MID_LENGTH,
    _DEFAULT_MID_RATIO,
    _DEFAULT_SHORT_COUNT,
    _DEFAULT_STEP,
    _DEFAULT_USE_MID_LENGTH,
    SHORT_COUNT_NAMES,
)


class _SlopeDialog(wx.Dialog):
    """Modal dialog for slope parameters."""

    def __init__(self, saved_state: dict):
        style = wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP | wx.RESIZE_BORDER
        wx.Dialog.__init__(self, None, title="IGI Slope — Параметры откоса", style=style)
        self.SetMinSize(wx.Size(420, 520))
        self.result_data: dict | None = None

        # Load saved state
        step_val = str(saved_state.get("step", _DEFAULT_STEP))
        bottom_offset_val = str(saved_state.get("bottom_offset", _DEFAULT_BOTTOM_OFFSET))
        sc_idx = saved_state.get("short_count", _DEFAULT_SHORT_COUNT)
        use_mid = saved_state.get("use_mid_length", _DEFAULT_USE_MID_LENGTH)
        mid_ratio_val = str(saved_state.get("mid_ratio", _DEFAULT_MID_RATIO))
        mid_len_val = str(saved_state.get("mid_length", _DEFAULT_MID_LENGTH))
        layer_val = saved_state.get("layer", _DEFAULT_LAYER)

        panel = wx.Panel(self)
        vsizer = wx.BoxSizer(wx.VERTICAL)

        # ═══════════ Параметры штрихов ═══════════
        prm_box = wx.StaticBox(panel, label="Параметры штрихов")
        psizer = wx.StaticBoxSizer(prm_box, wx.VERTICAL)

        # Шаг
        psizer.Add(wx.StaticText(psizer.GetStaticBox(), label="Шаг (ед. чертежа):"),
                   flag=wx.BOTTOM, border=4)
        self.step_ctrl = wx.TextCtrl(psizer.GetStaticBox(), value=step_val)
        if not saved_state:
            self.step_ctrl.SetFocus()
        psizer.Add(self.step_ctrl, flag=wx.EXPAND | wx.BOTTOM, border=8)

        # Отступ от нижнего контура
        psizer.Add(wx.StaticText(psizer.GetStaticBox(), label="Отступ от нижнего контура:"),
                   flag=wx.BOTTOM, border=4)
        self.bo_ctrl = wx.TextCtrl(psizer.GetStaticBox(), value=bottom_offset_val)
        psizer.Add(self.bo_ctrl, flag=wx.EXPAND | wx.BOTTOM, border=8)

        # Схема коротких штрихов
        psizer.Add(wx.StaticText(psizer.GetStaticBox(), label="Схема коротких штрихов:"),
                   flag=wx.BOTTOM, border=4)
        self.sc_combo = wx.Choice(
            psizer.GetStaticBox(), choices=SHORT_COUNT_NAMES,
        )
        self.sc_combo.SetSelection(min(sc_idx, len(SHORT_COUNT_NAMES) - 1))
        psizer.Add(self.sc_combo, flag=wx.EXPAND | wx.BOTTOM, border=8)

        # Флаг "использовать фикс. длину"
        self.use_mid_cb = wx.CheckBox(psizer.GetStaticBox(), label="Фиксированная длина коротких")
        self.use_mid_cb.SetValue(bool(use_mid))
        psizer.Add(self.use_mid_cb, flag=wx.BOTTOM, border=4)

        # midRatio (доля длины для коротких)
        fsizer = wx.BoxSizer(wx.HORIZONTAL)
        fsizer.Add(wx.StaticText(psizer.GetStaticBox(), label="Доля коротких:"),
                   flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        self.mr_ctrl = wx.TextCtrl(psizer.GetStaticBox(), value=mid_ratio_val, size=(80, -1))
        fsizer.Add(self.mr_ctrl, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=16)
        fsizer.Add(wx.StaticText(psizer.GetStaticBox(), label="Длина коротких:"),
                   flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        self.ml_ctrl = wx.TextCtrl(psizer.GetStaticBox(), value=mid_len_val, size=(80, -1))
        fsizer.Add(self.ml_ctrl, flag=wx.ALIGN_CENTER_VERTICAL)
        psizer.Add(fsizer, flag=wx.EXPAND | wx.BOTTOM, border=4)

        # Слой
        psizer.Add(wx.StaticText(psizer.GetStaticBox(), label="Слой:"),
                   flag=wx.BOTTOM, border=4)
        row_layer = wx.BoxSizer(wx.HORIZONTAL)
        self.layer_ctrl = wx.TextCtrl(psizer.GetStaticBox(), value=layer_val)
        self.layer_btn = wx.Button(psizer.GetStaticBox(), label="Выбрать...")
        row_layer.Add(self.layer_ctrl, proportion=1, flag=wx.RIGHT, border=4)
        row_layer.Add(self.layer_btn)
        psizer.Add(row_layer, flag=wx.EXPAND | wx.BOTTOM, border=4)

        vsizer.Add(psizer, flag=wx.EXPAND | wx.BOTTOM, border=12)

        # ═══ Инфо об объектах ═══
        info_box = wx.StaticBox(panel, label="Объекты")
        isizer = wx.StaticBoxSizer(info_box, wx.VERTICAL)

        self.top_status = wx.StaticText(isizer.GetStaticBox(), label="(-) Верхний контур не выбран")
        isizer.Add(self.top_status, flag=wx.BOTTOM, border=2)
        self.bottom_status = wx.StaticText(isizer.GetStaticBox(), label="(-) Нижний контур не выбран")
        isizer.Add(self.bottom_status, flag=wx.BOTTOM, border=2)

        vsizer.Add(isizer, flag=wx.EXPAND | wx.BOTTOM, border=12)

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
        self.Bind(wx.EVT_BUTTON, self._on_pick_layer, self.layer_btn)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self._on_cancel, id=wx.ID_CANCEL)

        self.CenterOnScreen()

    def set_object_status(self, top_ok: bool, bottom_ok: bool) -> None:
        if top_ok:
            self.top_status.SetLabel("(+) Верхний контур выбран")
            self.top_status.SetForegroundColour(wx.Colour(0, 100, 0))
        else:
            self.top_status.SetLabel("(-) Верхний контур не выбран")
            self.top_status.SetForegroundColour(wx.Colour(140, 140, 140))
        if bottom_ok:
            self.bottom_status.SetLabel("(+) Нижний контур выбран")
            self.bottom_status.SetForegroundColour(wx.Colour(0, 100, 0))
        else:
            self.bottom_status.SetLabel("(-) Нижний контур не выбран")
            self.bottom_status.SetForegroundColour(wx.Colour(140, 140, 140))

    def _on_pick_layer(self, evt) -> None:
        from pyrx import Ed
        res = Ed.Editor.entSel("\nВыберите объект на целевом слое: ")
        if res[0] != Ed.PromptStatus.eOk:
            return
        try:
            ent = Db.Entity(res[1], Db.OpenMode.kForRead)
            lt = Db.LayerTableRecord(ent.layerId(), Db.OpenMode.kForRead)
            self.layer_ctrl.SetValue(lt.getName())
            lt.close()
            ent.close()
        except Exception:
            wx.MessageBox("Не удалось определить слой.", "Ошибка",
                          wx.OK | wx.ICON_ERROR)

    def _on_ok(self, evt) -> None:
        try:
            step = float(self.step_ctrl.GetValue().replace(",", "."))
            if step <= 0:
                raise ValueError
        except (ValueError, AttributeError):
            wx.MessageBox("Шаг должен быть положительным числом.", "Ошибка",
                          wx.OK | wx.ICON_ERROR)
            return
        try:
            bo = float(self.bo_ctrl.GetValue().replace(",", "."))
            if bo < 0:
                raise ValueError
        except (ValueError, AttributeError):
            wx.MessageBox("Отступ должен быть неотрицательным числом.", "Ошибка",
                          wx.OK | wx.ICON_ERROR)
            return
        try:
            mr = float(self.mr_ctrl.GetValue().replace(",", "."))
            if not (0.0 <= mr <= 1.0):
                raise ValueError
        except (ValueError, AttributeError):
            wx.MessageBox("Доля коротких должна быть числом от 0 до 1.", "Ошибка",
                          wx.OK | wx.ICON_ERROR)
            return
        try:
            ml = float(self.ml_ctrl.GetValue().replace(",", "."))
            if ml < 0:
                raise ValueError
        except (ValueError, AttributeError):
            wx.MessageBox("Длина коротких должна быть неотрицательным числом.", "Ошибка",
                          wx.OK | wx.ICON_ERROR)
            return

        self.result_data = {
            "action": "ok",
            "step": step,
            "bottom_offset": bo,
            "short_count": self.sc_combo.GetSelection(),
            "use_mid_length": self.use_mid_cb.GetValue(),
            "mid_ratio": mr,
            "mid_length": ml,
            "layer": self.layer_ctrl.GetValue().strip(),
        }
        evt.Skip()

    def _on_cancel(self, evt) -> None:
        self.result_data = None
        evt.Skip()


def _show_dialog(
    saved_state: dict,
    top_selected: bool = False,
    bottom_selected: bool = False,
) -> dict | None:
    """Show wx dialog. Returns dict or None if cancelled."""
    res_override = Ap.ResourceOverride()
    dlg = _SlopeDialog(saved_state)
    try:
        dlg.set_object_status(top_selected, bottom_selected)
        if dlg.ShowModal() == wx.ID_OK:
            return dlg.result_data
        return None
    except Exception as e:
        print(f"\n[IGI Tools] Ошибка UI: {e}")
        return None
    finally:
        dlg.Destroy()
        del res_override


class _RadiusEditSlider(wx.Dialog):
    """Modeless dialog: radius (how many neighbours) + power (falloff steepness)."""

    def __init__(self, total_strokes: int, sel_idx: int, is_closed: bool):
        style = wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP
        wx.Dialog.__init__(self, None, title="Редактирование откоса", style=style)
        self.SetMinSize(wx.Size(280, 120))

        # Максимальный радиус
        if is_closed:
            max_radius = total_strokes // 2
        else:
            max_left = sel_idx
            max_right = total_strokes - 1 - sel_idx
            max_radius = max(max_left, max_right)

        # Начальный радиус — примерно треть от макс, но не меньше 1
        default_radius = max(1, min(max_radius, max_radius // 3))

        panel = wx.Panel(self)
        vsizer = wx.BoxSizer(wx.VERTICAL)

        # ── Радиус (количество соседей по обе стороны) ──
        vsizer.Add(wx.StaticText(panel, label="Радиус (штрихов по обе стороны):"),
                   flag=wx.BOTTOM, border=2)
        self.slider_radius = wx.Slider(
            panel, value=default_radius, minValue=1, maxValue=max_radius,
            size=(220, -1),
            style=wx.SL_HORIZONTAL | wx.SL_LABELS | wx.SL_AUTOTICKS,
        )
        vsizer.Add(self.slider_radius, flag=wx.EXPAND | wx.BOTTOM, border=8)

        # ── Пояснение ──
        info = wx.StaticText(panel, label="Линейное затухание от выбранного штриха\n"
                                          "до края радиуса")
        info.SetForegroundColour(wx.Colour(100, 100, 100))
        vsizer.Add(info, flag=wx.ALIGN_CENTER)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(vsizer, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        panel.SetSizer(outer)
        self.Fit()
        self.SetPosition(wx.Point(20, 80))

    @property
    def radius(self) -> int:
        return self.slider_radius.GetValue()
