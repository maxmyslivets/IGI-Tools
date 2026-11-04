"""Сервис ЦМР: единственный владелец подключённых GeoTIFF (rasterio)."""

from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

NODATA_MIN = -1000.0
NODATA_MAX = 10000.0

# Путь -> {"dataset": rasterio dataset, "active": bool}. Порядок = порядок подключения.
_dems: dict[str, dict] = {}


# ─── Состояние ────────────────────────────────────────────────────────


def is_loaded() -> bool:
    """True, если подключена хотя бы одна ЦМР."""
    return bool(_dems)


def get_paths() -> list[str]:
    """Пути всех подключённых ЦМР в порядке подключения."""
    return list(_dems)


def get_path() -> str | None:
    """Путь основной (последней подключённой) ЦМР или None."""
    for path in reversed(get_paths()):
        return path
    return None


def get_active_paths() -> list[str]:
    """Пути активных ЦМР, используемых для определения высот."""
    return [p for p, info in _dems.items() if info["active"]]


def is_active(path: str) -> bool:
    """Активна ли ЦМР по пути."""
    info = _dems.get(path)
    return bool(info and info["active"])


def set_active(path: str, active: bool) -> None:
    """Включает/выключает ЦМР для определения высот."""
    info = _dems.get(path)
    if info is None:
        return
    info["active"] = bool(active)


def load(path: str, active: bool = True) -> bool:
    """Подключает GeoTIFF, не выгружая остальные. False при ошибке."""
    if path in _dems:
        _dems[path]["active"] = _dems[path]["active"] or active
        save_last_path(path)
        return True
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
    _dems[path] = {"dataset": dataset, "active": bool(active)}
    save_last_path(path)
    print(f"[IGI Tools] ЦМР подключена: {path}")
    return True


def unload(path: str | None = None) -> None:
    """Закрывает одну ЦМР (по пути) или все сразу, если path не задан."""
    global _dems
    if path is None:
        for info in _dems.values():
            _close_dataset(info["dataset"])
        _dems = {}
    else:
        info = _dems.pop(path, None)
        if info is not None:
            _close_dataset(info["dataset"])
    _persist()


def _close_dataset(dataset) -> None:
    try:
        dataset.close()
    except Exception:
        traceback.print_exc()


def get_elevation(x: float, y: float) -> float | None:
    """Высота в точке (x, y) из первой активной ЦМР с данными, или None."""
    if not _dems:
        return None
    try:
        import math
        import numpy as np

        for path, info in _dems.items():
            if not info["active"]:
                continue
            try:
                z_raw = next(info["dataset"].sample([(x, y)], masked=True))[0]
            except Exception:
                continue
            if np.ma.is_masked(z_raw):
                continue
            z = float(z_raw)
            if math.isnan(z) or z < NODATA_MIN or z > NODATA_MAX:
                continue
            return z
    except Exception:
        traceback.print_exc()
    return None


# ─── Настройки в %APPDATA%/IGI-Tools ─────────────────────────────────


def _get_settings_path() -> Path:
    """Возвращает путь к файлу настроек в %APPDATA%/IGI-Tools."""
    app_data = os.environ.get("APPDATA", str(Path.home()))
    settings_dir = Path(app_data) / "IGI-Tools"
    settings_dir.mkdir(parents=True, exist_ok=True)
    return settings_dir / "dem_tracker_settings.json"


def _load_settings() -> dict:
    """Загружает настройки из JSON."""
    try:
        with open(_get_settings_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_settings(data: dict) -> None:
    """Сохраняет настройки в JSON."""
    try:
        with open(_get_settings_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _persist() -> None:
    """Сохраняет список подключённых ЦМР (пути + активность)."""
    data = _load_settings()
    data["dems"] = [
        {"path": p, "active": info["active"]} for p, info in _dems.items()
    ]
    last = get_path()
    if last is not None:
        data["last_dem_path"] = last
    _save_settings(data)


def last_path() -> str | None:
    """Путь к последней ЦМР из файла настроек или None."""
    path = _load_settings().get("last_dem_path", "")
    if path and Path(path).exists():
        return path
    return None


def save_last_path(path: str) -> None:
    """Сохраняет путь к последней ЦМР в файл настроек."""
    data = _load_settings()
    data["last_dem_path"] = path
    # для консистентности обновляем путь в списке, если он уже есть
    dems = data.get("dems", [])
    found = False
    for item in dems:
        if item.get("path") == path:
            item["active"] = True
            found = True
            break
    if not found:
        dems.append({"path": path, "active": True})
        data["dems"] = dems
    _save_settings(data)