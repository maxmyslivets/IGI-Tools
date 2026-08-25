"""Перезагрузка всех команд IGI Tools через importlib.reload."""

from __future__ import annotations

import importlib
import sys
import traceback

from pyrx import command


def _discover_command_modules() -> tuple[str, ...]:
    """Взять список команд из __all__ модуля __init__.py (исключая сам reload_all)."""
    from igi_tools.commands import __all__ as cmd_names

    prefix = "igi_tools.commands."
    return tuple(
        prefix + name
        for name in cmd_names
        if name not in ("reload_all", "__init__")
    )


@command(name="IGI_RELOAD_ALL")
def reload_all() -> None:
    """Перезагрузить все модули команд IGI Tools (для разработки)."""
    modules = _discover_command_modules()
    failed: list[tuple[str, Exception]] = []

    for mod_name in modules:
        try:
            importlib.reload(sys.modules[mod_name])
            print(f"  ✓  {mod_name}")
        except Exception as exc:
            failed.append((mod_name, exc))

    if failed:
        print("\n❌ Ошибки при перезагрузке:")
        for mod_name, exc in failed:
            print(f"  ✗  {mod_name}")
            for line in traceback.format_exception(type(exc), exc, exc.__traceback__):
                print(f"     {line.rstrip()}")
        print(f"\nПерезагружено: {len(modules) - len(failed)}/{len(modules)}")
    else:
        print(f"\n✅ Все {len(modules)} команд перезапущены успешно.")
