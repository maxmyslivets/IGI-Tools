"""Пути к ресурсам бандла IGI Tools."""

from __future__ import annotations

from pathlib import Path

TEMPLATE_NAME = "template.dwg"
TEMPLATE_DEFAULT_NAME = "template.default.dwg"
TEMPLATE_BACKUP_NAME = "template.dwg.bak"


def get_resources_dir() -> Path:
    """Каталог Resources бандла или resources/ в исходниках репозитория."""
    here = Path(__file__).resolve()
    # Bundle: .../Contents/Python/igi_tools/paths.py → parents[2] = Contents
    # Repo:   .../python/igi_tools/paths.py → parents[2] = корень репо
    candidates = (
        here.parents[2] / "Resources",
        here.parents[2] / "resources",
    )
    for path in candidates:
        if path.is_dir():
            return path
    return candidates[0]


def get_template_path() -> Path:
    """Активный шаблон (пользовательский или из дистрибутива)."""
    return get_resources_dir() / TEMPLATE_NAME


def get_template_default_path() -> Path:
    """Заводской шаблон из установщика (всегда актуальная версия дистрибутива)."""
    resources = get_resources_dir()
    default = resources / TEMPLATE_DEFAULT_NAME
    if default.is_file():
        return default
    # В исходниках репо лежит только resources/template.dwg
    return resources / TEMPLATE_NAME


def get_template_backup_path() -> Path:
    """Предыдущий активный шаблон после IGI_LOAD_TEMPLATE."""
    return get_resources_dir() / TEMPLATE_BACKUP_NAME
