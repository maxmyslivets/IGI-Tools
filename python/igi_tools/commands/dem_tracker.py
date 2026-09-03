"""Отслеживание высоты DEM: мониторинг Z-значений из GeoTIFF под курсором."""

from __future__ import annotations

import json
import os
import time
import traceback
from pathlib import Path

from pyrx import command, Ap


# Глобальное состояние
# ——— монитор ———
tiff_monitor = None
# ——— оверлей ———
_overlay = None
_overlay_text = None
_overlay_shown = False
# ——— данные с последнего тика monitorInputPoint ———
_last_z_value = "0.00"
_last_input_time = 0.0
_cursor_pos = (0, 0)
_overlay_update_pending = False


# ─── Сохранение/загрузка последнего пути ─────────────────────────────


def _get_settings_path() -> Path:
    """Возвращает путь к файлу настроек в %APPDATA%/IGI-Tools."""
    app_data = os.environ.get("APPDATA", str(Path.home()))
    settings_dir = Path(app_data) / "IGI-Tools"
    settings_dir.mkdir(parents=True, exist_ok=True)
    return settings_dir / "dem_tracker_settings.json"


def _save_last_path(tiff_path: str) -> None:
    """Сохраняет путь к последнему файлу DEM."""
    try:
        with open(_get_settings_path(), "w", encoding="utf-8") as f:
            json.dump({"last_dem_path": tiff_path}, f)
    except Exception:
        pass


def _load_last_path() -> str | None:
    """Загружает путь к последнему файлу DEM. Возвращает None, если пути нет."""
    try:
        settings_path = _get_settings_path()
        if settings_path.exists():
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                path = data.get("last_dem_path", "")
                if path and Path(path).exists():
                    return path
    except Exception:
        pass
    return None


# ─── Остановка трекинга (внутренняя) ────────────────────────────────


def _stop_tracking_internal() -> None:
    """Останавливает мониторинг и закрывает dataset. НЕ закрывает окно."""
    global tiff_monitor, _last_z_value

    if tiff_monitor is not None:
        try:
            manager = Ap.curDoc().inputPointManager()
            manager.removePointMonitor(tiff_monitor)
        except Exception:
            pass
        tiff_monitor.close()
        tiff_monitor = None

    _last_z_value = "0.00"


# ─── Построитель монитора ────────────────────────────────────────────


def _build_monitor(tiff_path):
    """Создаёт экземпляр подкласса InputPointMonitor для указанного GeoTIFF."""
    from pyrx import Ed

    import rasterio

    dataset = rasterio.open(tiff_path)
    print(f"\n[PyRx] DEM файл {tiff_path} подключён.\n")

    class _GeoTiffTrackerImpl(Ed.InputPointMonitor):
        """InputPointMonitor, считывающий Z-значения из GeoTIFF под курсором."""

        def __init__(self):
            Ed.InputPointMonitor.__init__(self)
            self.dataset = dataset
            self.current_text = None

        def monitorInputPoint(self, input, output):
            try:
                pt = input.rawPoint()
                generator = self.dataset.sample([(pt.x, pt.y)])
                z_val = next(generator)[0]

                if z_val < -1000 or z_val > 10000:
                    z_val = 0.0

                global _last_z_value, _last_input_time, _cursor_pos
                _last_z_value = f"{z_val:.2f}"
                _last_input_time = time.monotonic()

                # Захватываем реальную позицию мыши на экране
                _cursor_pos = _get_cursor_screen_pos()
                # Планируем мгновенное обновление оверлея в потоке wx
                _schedule_overlay_update()

                # msg = f"\rX={pt.x:.3f}м, Y={pt.y:.3f}м | Z={z_val:.2f}м"
                # print(msg)

            except Exception:
                traceback.print_exc()

        def close(self):
            try:
                self.dataset.close()
            except Exception:
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
    """Делает wx-окно прозрачным для мыши — клики/наведение проходят сквозь него."""
    import ctypes

    hwnd = window.GetHandle()
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_NOACTIVATE = 0x08000000

    current = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    new_style = current | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)


# ─── Асинхронное обновление оверлея ─────────────────────────────────


def _schedule_overlay_update():
    """Планирует перемещение оверлея через wx.CallAfter (не чаще 1 раза)."""
    global _overlay_update_pending
    if _overlay_update_pending:
        return
    _overlay_update_pending = True
    import wx

    wx.CallAfter(_apply_overlay_position)


def _apply_overlay_position():
    """Применяет последнюю позицию курсора к оверлею и обновляет текст с высотой."""
    import wx

    global _overlay_update_pending, _overlay, _overlay_text, _cursor_pos, _last_z_value
    _overlay_update_pending = False
    if _overlay is None:
        return
    try:
        _overlay.SetPosition(wx.Point(_cursor_pos[0] + 30, _cursor_pos[1] - 30))
        if _overlay_text is not None:
            _overlay_text.SetLabel(f"Z: {_last_z_value} м")
    except Exception:
        pass


# ─── Оверлей (только текст Z, без окна) ────────────────────────────


def _create_overlay():
    """Создаёт прозрачный оверлей с Z-высотой, следующий за курсором."""
    import wx
    from pyrx import Ap

    global _overlay, _overlay_text, _overlay_shown

    _res = Ap.ResourceOverride()

    overlay = wx.Frame(
        None, -1, "",
        style=wx.FRAME_NO_TASKBAR | wx.STAY_ON_TOP | wx.BORDER_NONE,
        size=wx.Size(140, 32),
    )
    overlay.SetBackgroundColour(wx.Colour(20, 20, 20))
    overlay.SetTransparent(200)
    _make_window_clickthrough(overlay)

    text = wx.StaticText(overlay, -1, "Z: 0.00 м")
    text.SetFont(
        wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_LIGHT)
    )
    text.SetForegroundColour(wx.WHITE)

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(text, 1, wx.ALIGN_CENTER | wx.ALL, 4)
    overlay.SetSizer(sizer)
    sizer.Fit(overlay)
    overlay.Show()

    _overlay = overlay
    _overlay_text = text
    _overlay_shown = True
    return overlay


def _destroy_overlay():
    """Уничтожает оверлей и сбрасывает глобалы."""
    global _overlay, _overlay_text, _overlay_shown, _overlay_update_pending, _cursor_pos
    _overlay_update_pending = False
    _cursor_pos = (0, 0)
    if _overlay is not None:
        try:
            _overlay.Close()
            _overlay.Destroy()
        except Exception:
            pass
        _overlay = None
        _overlay_text = None
        _overlay_shown = False


# ─── Запуск трекинга (внутренний) ────────────────────────────────────


# ─── Запуск трекинга (внутренний) ────────────────────────────────────


def _start_tracking(tiff_path: str) -> bool:
    """Строит монитор, запускает трекинг и открывает оверлей."""
    global tiff_monitor, _overlay

    print(f"\n[IGI Tools] Выбран DEM: {tiff_path}")

    try:
        monitor = _build_monitor(tiff_path)
    except ImportError:
        print(
            "\n[IGI Tools] Модуль 'rasterio' не установлен. "
            "Выполните: pip install rasterio"
        )
        return False
    except Exception as exc:
        print(f"\n[IGI Tools] Не удалось открыть растр: {exc}")
        traceback.print_exc()
        return False

    try:
        manager = Ap.curDoc().inputPointManager()
        manager.addPointMonitor(monitor)
    except AttributeError as exc:
        print(
            "\n[IGI Tools] Ваша версия PyRx не поддерживает addPointMonitor. "
            f"{exc}"
        )
        monitor.close()
        return False

    tiff_monitor = monitor
    _save_last_path(tiff_path)

    # Создать оверлей
    try:
        _create_overlay()
    except Exception as exc:
        print(
            "\n[IGI Tools] Не удалось открыть оверлей. "
            f"Трекинг работает в консоли. Ошибка: {exc}"
        )

    print("\n[IGI Tools] Мониторинг DEM запущен.")
    return True


# ─── Команды ─────────────────────────────────────────────────────────


def _switch_tiff(new_path: str):
    """Переключает монитор на новый TIFF-файл, не пересоздавая оверлей."""
    global tiff_monitor, _last_input_time, _overlay_update_pending

    if tiff_monitor is not None:
        try:
            manager = Ap.curDoc().inputPointManager()
            manager.removePointMonitor(tiff_monitor)
        except Exception:
            pass
        tiff_monitor.close()
        tiff_monitor = None

    try:
        new_monitor = _build_monitor(new_path)
        manager = Ap.curDoc().inputPointManager()
        manager.addPointMonitor(new_monitor)
        tiff_monitor = new_monitor
        _save_last_path(new_path)

        global _last_z_value
        _last_z_value = "0.00"
        _last_input_time = time.monotonic()
        _overlay_update_pending = False

        if _overlay_text:
            _overlay_text.SetLabel("Z: 0.00 м")

        print(f"\n[IGI Tools] Переключено на DEM: {new_path}")
    except Exception:
        traceback.print_exc()


@command(name="IGI_DEM_TRACKER")
def dem_tracker():
    """Запуск/остановка мониторинга Z-значений из цифровой модели рельефа GeoTIFF."""
    global tiff_monitor

    if tiff_monitor is not None:
        dem_tracker_stop()
        return

    # Последний файл
    last_path = _load_last_path()
    if last_path:
        print(f"\n[IGI Tools] Автоматическая загрузка: {last_path}")
        _start_tracking(last_path)
        return

    # Запросить файл
    from pyrx import Ed

    try:
        tiff_path = Ed.Core.getFileD(
            "Select GeoTIFF (DEM)", "", "tif;tiff", 0
        )
        if not tiff_path:
            print("\n[IGI Tools] Выбор файла отменён.")
            return
    except Exception:
        print("\n[IGI Tools] Ошибка открытия диалога выбора файла.")
        traceback.print_exc()
        return

    _start_tracking(tiff_path)


@command(name="IGI_DEM_TRACKER_SELECT_FILE")
def dem_tracker_select_file():
    """Выбор нового GeoTIFF для активного мониторинга DEM."""

    from pyrx import Ed

    try:
        new_path = Ed.Core.getFileD(
            "Select GeoTIFF (DEM)", "", "tif;tiff", 0
        )
        if not new_path:
            print("\n[IGI Tools] Выбор файла отменён.")
            return
    except Exception:
        print("\n[IGI Tools] Ошибка открытия диалога выбора файла.")
        traceback.print_exc()
        return

    _switch_tiff(new_path)


@command(name="IGI_DEM_TRACKER_STOP")
def dem_tracker_stop():
    """Остановка мониторинга Z-значений из GeoTIFF и закрытие оверлея."""
    global tiff_monitor

    if tiff_monitor is not None:
        _destroy_overlay()
        _stop_tracking_internal()
        print("\n[IGI Tools] Мониторинг DEM остановлен.")
    else:
        print("\n[IGI Tools] Активный мониторинг DEM отсутствует.")
