"""Дем-трекер: визуализация высоты ЦМР под курсором в оверлее.

Загруженной ЦМР (GeoTIFF) владеет сервис igi_tools.dem. Трекер на каждом
тике читает высоту через dem.get_elevation() и не управляет её жизненным
циклом: остановка трекера не выгружает ЦМР.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass

from pyrx import command, Ap


@dataclass
class _TrackerState:
    monitor: object = None           # _GeoTiffTrackerImpl instance
    overlay: object = None           # wx.Frame
    overlay_text: object = None      # wx.StaticText
    overlay_shown: bool = False
    last_z_value: str = "—"
    cursor_pos: tuple = (0, 0)
    enabled: bool = False            # user explicitly turned tracker ON
    overlay_update_pending: bool = False
    reactor: object = None           # Ap.DocManagerReactor
    tiff_path: str = ""              # last used DEM path (to reattach on doc switch)
    autocad_hwnd: int = 0
    last_input_time: float = 0.0


_state = _TrackerState()


class _TrackerDocReactor(Ap.DocManagerReactor):
    """Переподключает монитор к активному документу при переключении."""

    def documentToBeDeactivated(self, doc, /):
        try:
            if _state.monitor is None:
                return
            try:
                doc.inputPointManager().removePointMonitor(_state.monitor)
            except Exception:
                pass
            try:
                _state.monitor.close()
            except Exception:
                pass
            _state.monitor = None
        except Exception:
            traceback.print_exc()

    def documentActivated(self, doc, /):
        try:
            if not _state.enabled or _state.monitor is not None:
                return
            _attach_monitor_to_doc(doc)
            _create_overlay()
        except Exception:
            traceback.print_exc()

    def documentToBeDestroyed(self, doc, /):
        try:
            _destroy_overlay()
            # SAFE: close monitor WITHOUT touching the dying document's InputPointManager
            _close_monitor()
            _state.enabled = False
        except Exception:
            traceback.print_exc()


# ─── Остановка трекинга (внутренняя) ────────────────────────────────


def _stop_tracking_internal() -> None:
    """Снимает монитор и сбрасывает состояние. ЦМР (igi_tools.dem) не затрагивается."""
    if _state.reactor is not None:
        try:
            _state.reactor.removeReactor()
        except Exception:
            pass
        _state.reactor = None
    if _state.monitor is not None:
        try:
            Ap.curDoc().inputPointManager().removePointMonitor(_state.monitor)
        except Exception:
            pass
        _close_monitor()
    _state.last_z_value = "—"
    _state.enabled = False


def _close_monitor() -> None:
    """Закрывает Python-объект монитора, не трогая InputPointManager документа."""
    if _state.monitor is not None:
        try:
            _state.monitor.close()
        except Exception:
            pass
        _state.monitor = None
        _state.last_z_value = "—"


# ─── Построитель монитора ────────────────────────────────────────────


def _build_monitor():
    """Создаёт экземпляр подкласса InputPointMonitor для отслеживания высоты."""
    from pyrx import Ed

    class _GeoTiffTrackerImpl(Ed.InputPointMonitor):
        def __init__(self):
            Ed.InputPointMonitor.__init__(self)

        def monitorInputPoint(self, input, output):
            try:
                pt = input.rawPoint()
                from igi_tools import dem

                z = dem.get_elevation(pt.x, pt.y)
                _state.last_z_value = "—" if z is None else f"{z:.2f}"
                _state.last_input_time = time.monotonic()
                _schedule_overlay_update()
            except Exception:
                traceback.print_exc()

        def close(self):
            pass

    return _GeoTiffTrackerImpl()


# ─── Вспомогательные функции Win32 ──────────────────────────────────


def _get_cursor_screen_pos():
    """Возвращает (x, y) позиции курсора в экранных координатах."""
    import ctypes

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = _POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _make_window_clickthrough(window):
    """Делает wx-окно прозрачным для мыши."""
    import ctypes

    hwnd = window.GetHandle()
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_NOACTIVATE = 0x08000000

    current = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    new_style = current | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)


# ─── Оверлей и обновление позиции ───────────────────────────────────


def _schedule_overlay_update():
    """Планирует перенос оверлея через wx.CallAfter; один pending-вызов за раз."""
    if _state.overlay_update_pending:
        return
    _state.overlay_update_pending = True
    try:
        import wx

        wx.CallAfter(_apply_overlay_position)
    except Exception:
        _state.overlay_update_pending = False
        traceback.print_exc()


def _apply_overlay_position():
    """Двигает оверлей за курсором, обновляет метку, прячет при сворачивании AutoCAD."""
    try:
        _state.overlay_update_pending = False
        if _state.overlay is None:
            return
        import wx

        _state.cursor_pos = _get_cursor_screen_pos()
        overlay = _state.overlay
        overlay.Move(wx.Point(_state.cursor_pos[0] + 7, _state.cursor_pos[1] - 30))
        if _state.overlay_text is not None:
            _state.overlay_text.SetLabel(f"Z: {_state.last_z_value} м")
        if _state.autocad_hwnd:
            import ctypes

            minimized = bool(ctypes.windll.user32.IsIconic(_state.autocad_hwnd))
            hidden = minimized or not bool(
                ctypes.windll.user32.IsWindowVisible(_state.autocad_hwnd)
            )
            if hidden and _state.overlay_shown:
                overlay.Hide()
                _state.overlay_shown = False
            elif not hidden and not _state.overlay_shown:
                overlay.Show()
                _state.overlay_shown = True
    except Exception:
        # Оверлей может быть уничтожен в момент вызова
        pass


def _create_overlay():
    """Создаёт прозрачный оверлей с Z-высотой, следующий за курсором."""
    if _state.overlay is not None:
        return _state.overlay
    import wx

    try:
        _res = Ap.ResourceOverride()
        overlay = wx.Frame(
            None, -1, "",
            style=wx.FRAME_NO_TASKBAR | wx.BORDER_NONE,
            size=wx.Size(100, 40),
        )
        overlay.SetBackgroundColour(wx.Colour(20, 20, 20))
        overlay.SetTransparent(200)
        _make_window_clickthrough(overlay)
        if _state.autocad_hwnd:
            import ctypes

            overlay_hwnd = overlay.GetHandle()
            GWLP_HWNDPARENT = -8
            ctypes.windll.user32.SetWindowLongPtrW(
                overlay_hwnd, GWLP_HWNDPARENT, _state.autocad_hwnd
            )

        text = wx.StaticText(overlay, -1, f"Z: {_state.last_z_value} м")
        text.SetFont(
            wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_LIGHT)
        )
        text.SetForegroundColour(wx.WHITE)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(text, 1, wx.ALIGN_LEFT | wx.ALL, 4)
        overlay.SetSizer(sizer)
        sizer.Fit(overlay)
        w, h = overlay.GetSize()
        overlay.SetMinSize(wx.Size(max(w, 80), max(h, 16)))
        overlay.SetSize(wx.Size(max(w, 80), max(h, 16)))
        overlay.Show()

        _state.overlay = overlay
        _state.overlay_text = text
        _state.overlay_shown = True
        return overlay
    except Exception as exc:
        print(
            "\n[IGI Tools] Не удалось открыть оверлей. "
            f"Трекинг работает в консоли. Ошибка: {exc}"
        )
        traceback.print_exc()
        return None


def _destroy_overlay():
    """Уничтожает оверлей и сбрасывает состояние."""
    _state.overlay_update_pending = False
    _state.cursor_pos = (0, 0)
    if _state.overlay is not None:
        try:
            _state.overlay.Close()
            _state.overlay.Destroy()
        except Exception:
            pass
        _state.overlay = None
        _state.overlay_text = None
        _state.overlay_shown = False


# ─── Подключение монитора к документу ────────────────────────────────


def _attach_monitor_to_doc(doc) -> bool:
    """Создаёт монитор и регистрирует его в inputPointManager документа."""
    try:
        monitor = _build_monitor()
    except Exception as exc:
        print(f"\n[IGI Tools] Не удалось создать монитор: {exc}")
        traceback.print_exc()
        return False
    try:
        doc.inputPointManager().addPointMonitor(monitor)
    except AttributeError as exc:
        print(
            "\n[IGI Tools] Ваша версия PyRx не поддерживает addPointMonitor. "
            f"{exc}"
        )
        monitor.close()
        return False
    _state.monitor = monitor
    return True


# ─── Запуск трекинга ────────────────────────────────────────────────


def _start_tracking(tiff_path: str) -> bool:
    """Подключает ЦМР через сервис igi_tools.dem, строит монитор и открывает оверлей."""
    from igi_tools import dem

    print(f"\n[IGI Tools] Выбран DEM: {tiff_path}")
    if not (dem.is_loaded() and tiff_path in dem.get_paths()):
        if not dem.load(tiff_path):
            return False

    _state.enabled = True
    _state.tiff_path = tiff_path
    try:
        _state.autocad_hwnd = Ap.Application.mainWnd() or 0
    except Exception:
        _state.autocad_hwnd = 0

    if _state.reactor is None:
        try:
            reactor = _TrackerDocReactor()
            reactor.addReactor()
            _state.reactor = reactor
        except Exception as exc:
            print(f"\n[IGI Tools] Не удалось зарегистрировать реактор документов: {exc}")
            _state.reactor = None

    if not _attach_monitor_to_doc(Ap.curDoc()):
        return False

    dem.save_last_path(tiff_path)
    _create_overlay()
    print("\n[IGI Tools] Мониторинг DEM запущен.")
    return True


# ─── Команды ─────────────────────────────────────────────────────────


@command(name="IGI_DEM_TRACKER")
def dem_tracker():
    """Запуск/остановка мониторинга Z-значений из цифровой модели рельефа GeoTIFF."""
    if _state.enabled:
        dem_tracker_stop()
        return

    from igi_tools import dem

    if dem.is_loaded():
        _start_tracking(dem.get_path())
        return

    last_path = dem.last_path()
    if last_path:
        print(f"\n[IGI Tools] Автоматическая загрузка: {last_path}")
        _start_tracking(last_path)
        return

    from pyrx import Ed

    try:
        tiff_path = Ed.Core.getFileD("Select GeoTIFF (DEM)", "", "tif;tiff", 0)
        if not tiff_path:
            print("\n[IGI Tools] Выбор файла отменён.")
            return
    except Exception:
        print("\n[IGI Tools] Ошибка открытия диалога выбора файла.")
        traceback.print_exc()
        return

    _start_tracking(tiff_path)


@command(name="IGI_DEM_MANAGER")
def dem_tracker_select_file():
    """Открывает окно управления подключёнными ЦМР."""
    from igi_tools.commands.dem_manager import _show_dialog

    try:
        _show_dialog()
    except Exception:
        print("\n[IGI Tools] Ошибка открытия диалога управления ЦМР.")
        traceback.print_exc()


@command(name="IGI_DEM_TRACKER_STOP")
def dem_tracker_stop():
    """Остановка мониторинга Z-значений из GeoTIFF и закрытие оверлея."""
    if _state.enabled:
        _destroy_overlay()
        _stop_tracking_internal()
        print("\n[IGI Tools] Мониторинг DEM остановлен.")
        print("\n[IGI Tools] ЦМР остаётся подключённой для других инструментов.")
    else:
        print("\n[IGI Tools] Активный мониторинг DEM отсутствует.")