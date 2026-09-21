"""Команды замены и сброса шаблона template.dwg."""

from __future__ import annotations

import shutil
import traceback
from pathlib import Path

from pyrx import Ed, command

from igi_tools.paths import (
    get_resources_dir,
    get_template_backup_path,
    get_template_default_path,
    get_template_path,
)


def _select_dwg_file() -> str:
    """Диалог выбора DWG через AutoCAD (acedGetFileD)."""
    try:
        path = Ed.Core.getFileD("Выберите шаблон DWG", "", "dwg", 0)
        return path or ""
    except Exception:
        return ""


@command(name="IGI_LOAD_TEMPLATE")
def load_template() -> None:
    """Скопировать выбранный DWG в Contents/Resources как template.dwg."""
    print("\n[IGI Tools] Загрузка пользовательского шаблона…")

    src = _select_dwg_file()
    if not src:
        print("[IGI Tools] Выбор файла отменён.")
        return

    src_path = Path(src)
    if not src_path.is_file():
        print(f"[IGI Tools] Файл не найден: {src_path}")
        return
    if src_path.suffix.lower() != ".dwg":
        print("[IGI Tools] Нужен файл с расширением .dwg.")
        return

    try:
        resources = get_resources_dir()
        resources.mkdir(parents=True, exist_ok=True)

        dest = get_template_path()
        bak = get_template_backup_path()

        if dest.is_file():
            if bak.is_file():
                bak.unlink()
            dest.rename(bak)
            print(f"[IGI Tools] Старый шаблон сохранён как {bak.name}")

        shutil.copy2(src_path, dest)
        print(f"[IGI Tools] Шаблон установлен:\n  {dest}")
    except Exception as exc:
        traceback.print_exc()
        print(f"[IGI Tools] Ошибка загрузки шаблона: {exc}")


@command(name="IGI_RESET_TEMPLATE")
def reset_template() -> None:
    """Восстановить template.dwg из заводского template.default.dwg (дистрибутив)."""
    print("\n[IGI Tools] Сброс шаблона к версии из установщика…")

    dest = get_template_path()
    default = get_template_default_path()

    if not default.is_file():
        print(f"[IGI Tools] Заводской шаблон не найден:\n  {default}")
        return

    try:
        resources = get_resources_dir()
        resources.mkdir(parents=True, exist_ok=True)
        shutil.copy2(default, dest)
        print(f"[IGI Tools] Шаблон восстановлен из дистрибутива:\n  {dest}")
    except Exception as exc:
        traceback.print_exc()
        print(f"[IGI Tools] Ошибка сброса шаблона: {exc}")
