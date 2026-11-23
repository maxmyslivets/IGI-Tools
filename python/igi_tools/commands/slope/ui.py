"""Slope wx dialog for parameters."""

from __future__ import annotations

import wx
from pyrx import Ap, Db

from igi_tools.commands.slope.config import (
    _DEFAULT_BOTTOM_OFFSET,
    _DEFAULT_LAYER,
    _DEFAULT_MID_LENGTH,
    _DEFAULT_MID_RATIO,
    _DEFAULT_STEP,
    _DEFAULT_USE_MID_LENGTH,
)

class _SlopeDialog(wx.Dialog):
    """Modal dialog for slope parameters."""

    def __init__(self, saved_state: dict):
        style = wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP | wx.RESIZE_BORDER
        wx.Dialog.__init__(self, None, title="IGI Slope — Параметры откоса", style=style)
        self.SetMinSize(wx.Size(294, 364))
        self.result_data: dict | None = None

        # Load saved state
        step_val = str(saved_state.get("step", _DEFAULT_STEP))
        bottom_offset_val = str(saved_state.get("bottom_offset", _DEFAULT_BOTTOM_OFFSET))
        use_mid = saved_state.get("use_mid_length", _DEFAULT_USE_MID_LENGTH)
        mid_ratio_val = str(saved_state.get("mid_ratio", _DEFAULT_MID_RATIO))
        mid_len_val = str(saved_state.get("mid_length", _DEFAULT_MID_LENGTH))
        layer_use_default = saved_state.get("use_default_layer", True)
        saved_layer = saved_state.get("layer", _DEFAULT_LAYER)

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
        psizer.Add(self.bo_ctrl, flag=wx.EXPAND | wx.BOTTOM, border=4)

        vsizer.Add(psizer, flag=wx.EXPAND | wx.BOTTOM, border=12)

        # ═══════════ Длина коротких штрихов ═══════════
        short_box = wx.StaticBox(panel, label="Длина коротких штрихов")
        ssizer = wx.StaticBoxSizer(short_box, wx.VERTICAL)

        self.cb_fixed = wx.CheckBox(ssizer.GetStaticBox(), label="Фиксированная:")
        self.cb_fixed.SetValue(bool(use_mid))
        row_fixed = wx.BoxSizer(wx.HORIZONTAL)
        row_fixed.Add(self.cb_fixed, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=4)
        self.ml_ctrl = wx.TextCtrl(ssizer.GetStaticBox(), value=mid_len_val, size=(56, -1))
        self.ml_ctrl.Enable(bool(use_mid))
        row_fixed.Add(self.ml_ctrl, flag=wx.ALIGN_CENTER_VERTICAL)
        ssizer.Add(row_fixed, flag=wx.BOTTOM, border=4)

        self.cb_ratio = wx.CheckBox(ssizer.GetStaticBox(), label="Относительная:")
        self.cb_ratio.SetValue(not bool(use_mid))
        row_ratio = wx.BoxSizer(wx.HORIZONTAL)
        row_ratio.Add(self.cb_ratio, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=4)
        self.mr_ctrl = wx.TextCtrl(ssizer.GetStaticBox(), value=mid_ratio_val, size=(56, -1))
        self.mr_ctrl.Enable(not bool(use_mid))
        row_ratio.Add(self.mr_ctrl, flag=wx.ALIGN_CENTER_VERTICAL)
        ssizer.Add(row_ratio, flag=wx.BOTTOM, border=4)

        self.Bind(wx.EVT_CHECKBOX, self._on_toggle_fixed, self.cb_fixed)
        self.Bind(wx.EVT_CHECKBOX, self._on_toggle_ratio, self.cb_ratio)

        vsizer.Add(ssizer, flag=wx.EXPAND | wx.BOTTOM, border=12)

        # ═══════════ Слой ═══════════
        layer_box = wx.StaticBox(panel, label="Слой")
        lsizer = wx.StaticBoxSizer(layer_box, wx.VERTICAL)

        # ── Чекбокс «По умолчанию» ──
        self.cb_use_default = wx.CheckBox(
            lsizer.GetStaticBox(),
            label=f"По умолчанию ({_DEFAULT_LAYER})",
        )
        self.cb_use_default.SetValue(layer_use_default)
        lsizer.Add(self.cb_use_default, flag=wx.BOTTOM, border=4)

        # ── Выпадающий список слоёв из чертежа ──
        self.layer_combo = wx.ComboBox(
            lsizer.GetStaticBox(),
            choices=[],
            style=wx.CB_DROPDOWN | wx.CB_READONLY,
        )
        lsizer.Add(self.layer_combo, flag=wx.EXPAND | wx.BOTTOM, border=4)

        # ── Заполняем выпадающий список ──
        dwg_names = self._get_layer_names_from_dwg()
        for n in dwg_names:
            self.layer_combo.Append(n)
        if saved_layer in dwg_names:
            self.layer_combo.SetValue(saved_layer)
        elif dwg_names:
            self.layer_combo.SetSelection(0)
        self.layer_combo.Enable(not layer_use_default)

        vsizer.Add(lsizer, flag=wx.EXPAND | wx.BOTTOM, border=12)

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
        self.Bind(wx.EVT_CHECKBOX, self._on_cb_use_default, self.cb_use_default)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self._on_cancel, id=wx.ID_CANCEL)

        self.CenterOnScreen()

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
            "short_count": 2,
            "mid_ratio": mr,
            "use_mid_length": self.cb_fixed.GetValue(),
            "mid_length": ml,
            "layer": self._get_selected_layer(),
            "use_default_layer": self.cb_use_default.GetValue(),
        }
        evt.Skip()

    def _on_cancel(self, evt) -> None:
        self.result_data = None
        evt.Skip()

    def _on_cb_use_default(self, evt) -> None:
        checked = self.cb_use_default.GetValue()
        self.layer_combo.Enable(not checked)

    def _get_layer_names_from_dwg(self) -> list[str]:
        """Get all layer names from the current drawing, excluding '0'."""
        try:
            db = Db.curDb()
            lt = Db.LayerTable(db.layerTableId(), Db.OpenMode.kForRead)
            names: list[str] = []
            for name, oid in lt:
                if name != "0":
                    names.append(name)
            lt.close()
            return sorted(names)
        except Exception as ex:
            print(f"[IGI Tools] _get_layer_names_from_dwg error: {ex}")
            return []

    def _get_selected_layer(self) -> str:
        if self.cb_use_default.GetValue():
            return _DEFAULT_LAYER
        val = self.layer_combo.GetValue().strip()
        return val if val else _DEFAULT_LAYER

    def _on_toggle_fixed(self, evt) -> None:
        checked = self.cb_fixed.GetValue()
        if checked:
            self.cb_ratio.SetValue(False)
            self.mr_ctrl.Enable(False)
            self.ml_ctrl.Enable(True)
        else:
            self.cb_ratio.SetValue(True)
            self.mr_ctrl.Enable(True)
            self.ml_ctrl.Enable(False)

    def _on_toggle_ratio(self, evt) -> None:
        checked = self.cb_ratio.GetValue()
        if checked:
            self.cb_fixed.SetValue(False)
            self.ml_ctrl.Enable(False)
            self.mr_ctrl.Enable(True)
        else:
            self.cb_fixed.SetValue(True)
            self.ml_ctrl.Enable(True)
            self.mr_ctrl.Enable(False)



def _show_dialog(
    saved_state: dict,
) -> dict | None:
    """Show wx dialog. Returns dict or None if cancelled."""
    res_override = Ap.ResourceOverride()
    dlg = _SlopeDialog(saved_state)
    try:
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
        self.SetMinSize(wx.Size(196, 60))

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
            size=(154, -1),
            style=wx.SL_HORIZONTAL | wx.SL_LABELS | wx.SL_AUTOTICKS,
        )
        vsizer.Add(self.slider_radius, flag=wx.EXPAND | wx.BOTTOM, border=8)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(vsizer, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        panel.SetSizer(outer)
        self.Fit()
        self.CenterOnScreen()

    @property
    def radius(self) -> int:
        return self.slider_radius.GetValue()
