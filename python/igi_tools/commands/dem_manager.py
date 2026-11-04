"""Окно управления подключёнными ЦМР (команда IGI_DEM_MANAGER)."""

from __future__ import annotations

import traceback

import wx

from pyrx import command

from igi_tools import dem

_DEM_WILDCARD = "GeoTIFF (*.tif;*.tiff)|*.tif;*.tiff"


class _DemManagerDialog(wx.Dialog):
    """Список подключённых ЦМР: активность, выгрузка, добавление."""

    def __init__(self, parent=None):
        wx.Dialog.__init__(
            self,
            parent,
            title="Менеджер ЦМР — подключённые растры",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.STAY_ON_TOP,
        )
        self.SetMinSize(wx.Size(640, 360))
        self._rows: list[tuple[str, wx.CheckBox]] = []

        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        self._list = wx.ScrolledWindow(panel)
        self._list.SetScrollRate(0, 20)
        self._list_sizer = wx.BoxSizer(wx.VERTICAL)
        self._list.SetSizer(self._list_sizer)
        root.Add(self._list, 1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)

        btns = wx.BoxSizer(wx.HORIZONTAL)
        add_btn = wx.Button(panel, label="Добавить ЦМР…")
        add_btn.Bind(wx.EVT_BUTTON, self._on_add)
        unload_all_btn = wx.Button(panel, label="Выгрузить все")
        unload_all_btn.Bind(wx.EVT_BUTTON, self._on_unload_all)
        close_btn = wx.Button(panel, wx.ID_CLOSE, label="Закрыть")
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        btns.Add(add_btn, flag=wx.RIGHT, border=8)
        btns.Add(unload_all_btn, flag=wx.RIGHT, border=8)
        btns.AddStretchSpacer(1)
        btns.Add(close_btn)

        root.Add(wx.StaticLine(panel), flag=wx.EXPAND | wx.TOP, border=8)
        root.Add(btns, flag=wx.EXPAND | wx.ALL, border=8)

        panel.SetSizer(root)
        self._rebuild()

    # ─── построение списка ──────────────────────────────────────────

    def _rebuild(self) -> None:
        """Перестраивает список строк из dem.get_paths()."""
        self._rows = []
        self._list_sizer.Clear(delete_windows=True)

        paths = dem.get_paths()
        if not paths:
            empty = wx.StaticText(self._list, label="Нет подключённых ЦМР")
            self._list_sizer.Add(empty, flag=wx.ALL, border=4)
        for path in paths:
            row = wx.BoxSizer(wx.HORIZONTAL)
            cb = wx.CheckBox(self._list, label=path)
            cb.SetValue(dem.is_active(path))
            cb.Bind(wx.EVT_CHECKBOX, lambda e, p=path: self._on_toggle(p))
            unload_btn = wx.Button(self._list, label="Выгрузить", style=wx.BU_EXACTFIT)
            unload_btn.Bind(wx.EVT_BUTTON, lambda e, p=path: self._on_unload(p))
            row.Add(cb, 1, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=2)
            row.Add(unload_btn, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=2)
            self._list_sizer.Add(row, flag=wx.EXPAND)
            self._rows.append((path, cb))

        self._list.FitInside()
        self.Fit()

    # ─── обработчики ────────────────────────────────────────────────

    def _on_toggle(self, path: str) -> None:
        """Переключает активность ЦМР."""
        for p, cb in self._rows:
            if p == path:
                dem.set_active(p, cb.GetValue())
                break

    def _on_unload(self, path: str) -> None:
        """Выгружает одну ЦМР."""
        dem.unload(path)
        self._rebuild()

    def _on_unload_all(self, _event) -> None:
        """Выгружает все ЦМР после подтверждения."""
        if not dem.is_loaded():
            return
        answer = wx.MessageBox(
            "Выгрузить все подключённые ЦМР?",
            "Подтверждение",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if answer == wx.YES:
            dem.unload()
            self._rebuild()

    def _on_add(self, _event) -> None:
        """Диалог выбора одного или нескольких GeoTIFF."""
        dlg = wx.FileDialog(
            self,
            "Добавить ЦМР (GeoTIFF)",
            wildcard=_DEM_WILDCARD,
            style=wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_FILE_MUST_EXIST,
        )
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        paths = dlg.GetPaths()
        dlg.Destroy()
        failed = [p for p in paths if not dem.load(p)]
        if failed:
            wx.MessageBox(
                "Не удалось открыть:\n" + "\n".join(failed),
                "Ошибка",
                wx.OK | wx.ICON_WARNING,
            )
        self._rebuild()


def _show_dialog() -> None:
    """Открывает модальный диалог управления ЦМР."""
    dlg = _DemManagerDialog()
    try:
        dlg.ShowModal()
    finally:
        dlg.Destroy()


@command(name="IGI_DEM_MANAGER")
def dem_manager() -> None:
    """Окно управления подключёнными ЦМР."""
    print("\n[IGI Tools] Запуск IGI_DEM_MANAGER…")
    try:
        _show_dialog()
    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: не удалось открыть окно управления ЦМР.")