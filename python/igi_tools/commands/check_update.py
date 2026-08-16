"""Команда проверки обновлений IGI Tools."""

from __future__ import annotations

from pyrx import command

from igi_tools.updater import check_update_interactive


@command(name="IGI_CHECK_UPDATE")
def check_update() -> None:
    """Проверить наличие новой версии на GitHub Releases."""
    check_update_interactive()
