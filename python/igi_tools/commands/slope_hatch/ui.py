"""Slope hatch wx dialog."""

from __future__ import annotations

import wx
from pyrx import Ap, Ed

from igi_tools.commands.slope_hatch.config import (
    _DEFAULT_LAYER_NAME,
    _DEFAULT_STEP,
    _MODE_NAMES,
)


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
            lsizer.GetStaticBox(),
            label=f"Использовать стандартный слой «{_DEFAULT_LAYER_NAME}»",
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

        self.layer_pick_result = wx.StaticText(lsizer.GetStaticBox(), label="")
        lsizer.Add(self.layer_pick_result, flag=wx.BOTTOM, border=4)

        row_create = wx.BoxSizer(wx.HORIZONTAL)
        self.layer_radio_create = wx.RadioButton(
            lsizer.GetStaticBox(), label="Создать",
        )
        self.layer_radio_create.SetValue(layer_mode == 2)
        self.layer_create_ctrl = wx.TextCtrl(
            lsizer.GetStaticBox(),
            value=custom_layer if layer_mode == 2 else "",
        )
        self.layer_create_ctrl.Enable(layer_mode == 2)
        row_create.Add(self.layer_radio_create, flag=wx.ALIGN_CENTER_VERTICAL)
        row_create.Add((4, 0))
        row_create.Add(
            self.layer_create_ctrl,
            proportion=1,
            flag=wx.ALIGN_CENTER_VERTICAL,
        )
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
    dlg = _ParamsDialog(brink_selected, toe_selected, saved_state)
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