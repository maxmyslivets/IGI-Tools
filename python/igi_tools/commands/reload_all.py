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


def _reload_module_tree(mod_name: str) -> list[str]:
    """Reload a module and all its submodules (if it's a package).
    Returns list of successfully reloaded names."""
    mod = sys.modules.get(mod_name)
    if mod is None:
        return []

    # Collect submodules first (before any reload invalidates the package state)
    submodules: list[str] = []
    if hasattr(mod, "__path__"):
        prefix = mod_name + "."
        submodules = sorted(
            name for name in sys.modules
            if name.startswith(prefix)
        )

    # Reload deepest submodules first, then the parent
    ok: list[str] = []
    for sub in submodules:
        try:
            importlib.reload(sys.modules[sub])
            ok.append(sub)
        except Exception:
            pass  # parent reload will catch errors

    try:
        importlib.reload(sys.modules[mod_name])
        ok.append(mod_name)
    except Exception:
        pass

    return ok


@command(name="IGI_RELOAD_ALL")
def reload_all() -> None:
    """Перезагрузить все модули команд IGI Tools (для разработки)."""
    modules = _discover_command_modules()
    failed: list[tuple[str, Exception]] = []
    reloaded: list[str] = []

    for mod_name in modules:
        try:
            ok = _reload_module_tree(mod_name)
            if ok:
                reloaded.extend(ok)
                print(f"  ✓  {mod_name}")
        except Exception as exc:
            failed.append((mod_name, exc))

    if failed:
        print("\n❌ Ошибки при перезагрузке:")
        for mod_name, exc in failed:
            print(f"  ✗  {mod_name}")
            for line in traceback.format_exception(type(exc), exc, exc.__traceback__):
                print(f"     {line.rstrip()}")
        print(f"\nПерезагружено: {len(reloaded)}/{len(modules)}")
    else:
        print(f"\n✅ Все {len(reloaded)} модулей команд перезапущены успешно.")
