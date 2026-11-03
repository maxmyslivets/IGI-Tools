"""Сервис ЦМР: единственный владелец загруженного GeoTIFF (rasterio)."""

from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

NODATA_MIN = -1000.0
NODATA_MAX = 10000.0

_dataset = None
_path: str | None = None


def is_loaded() -> bool:
    """True, если ЦМР подключена."""
    return _dataset is not None


def get_path() -> str | None:
    """Путь к подключённой ЦМР или None."""
    return _path


def load(path: str) -> bool:
    """Подключает GeoTIFF. False при ошибке, True при успехе."""
    global _dataset, _path
    if is_loaded():
        unload()
    try:
        import rasterio
    except ImportError:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: не установлен rasterio. Установите: pip install rasterio")
        return False
    try:
        dataset = rasterio.open(path)
    except Exception:
        traceback.print_exc()
        print(f"[IGI Tools] Ошибка: не удалось открыть ЦМР: {path}")
        return False
    _dataset = dataset
    _path = path
    print(f"[IGI Tools] ЦМР подключена: {path}")
    return True


def unload() -> None:
    """Закрывает dataset и сбрасывает состояние."""
    global _dataset, _path
    if _dataset is not None:
        try:
            _dataset.close()
        except Exception:
            traceback.print_exc()
    _dataset = None
    _path = None


def get_elevation(x: float, y: float) -> float | None:
    """Высота в точке (x, y) или None, если ЦМР не подключена или точка вне ЦМР."""
    if not is_loaded():
        return None
    try:
        import math
        import numpy as np
        z_raw = next(_dataset.sample([(x, y)], masked=True))[0]
        if np.ma.is_masked(z_raw):
            return None
        z = float(z_raw)
        if math.isnan(z) or z < NODATA_MIN or z > NODATA_MAX:
            return None
        return z
    except Exception:
        traceback.print_exc()
        return None


# ─── Последний путь ЦМР (настройки в %APPDATA%/IGI-Tools) ─────────────


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


def last_path() -> str | None:
    """Путь к последней ЦМР из файла настроек или None."""
    path = _load_last_path()
    if path is not None and not Path(path).exists():
        return None
    return path


def save_last_path(path: str) -> None:
    """Сохраняет путь к последней ЦМР в файл настроек."""
    _save_last_path(path)