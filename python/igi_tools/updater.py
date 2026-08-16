"""Проверка обновлений IGI Tools через GitHub Releases.

Скачивание установщика намеренно не делается внутри процесса CAD:
urllib + wx.ProgressDialog блокировали AutoCAD (в т.ч. при «Отмена»),
и процесс становился неуправляемым. Вместо этого открывается прямая
ссылка на asset в браузере — загрузкой и отменой занимается система.
"""

from __future__ import annotations

import json
import re
import ssl
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

GITHUB_OWNER = "maxmyslivets"
GITHUB_REPO = "IGI-Tools"
RELEASES_API = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
RELEASES_PAGE = (
    f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
INSTALLER_NAME_RE = re.compile(r"^IGITools-setup-.*\.exe$", re.IGNORECASE)
USER_AGENT = "IGI-Tools-Updater"

_check_started = False
_declined_this_session = False
_resource_override = None  # Ap.ResourceOverride на время UI обновления


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag: str
    download_url: str
    asset_name: str
    size: int
    notes: str


def get_installed_version() -> str:
    """Версия из PackageContents.xml (AppVersion), иначе VERSION / 0.0.0."""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "PackageContents.xml",  # установленный bundle
        here.parents[2] / "bundle" / "PackageContents.xml",  # исходники репо
    ]
    for xml_path in candidates:
        if not xml_path.is_file():
            continue
        try:
            root = ET.parse(xml_path).getroot()
            ver = (root.attrib.get("AppVersion") or "").strip()
            if ver:
                return ver
        except ET.ParseError:
            continue

    for ver_file in (
        here.parents[3] / "VERSION",
        here.parents[2] / "VERSION",
    ):
        if ver_file.is_file():
            text = ver_file.read_text(encoding="utf-8").strip()
            if text:
                return text
    return "0.0.0"


def _parse_version(text: str) -> tuple[int, int, int]:
    cleaned = text.strip().lstrip("vV")
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", cleaned)
    if not match:
        return (0, 0, 0)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def is_newer(remote: str, local: str) -> bool:
    return _parse_version(remote) > _parse_version(local)


def _http_get_json(url: str, timeout: float = 15.0) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _pick_installer_asset(assets: list[dict], version: str) -> dict | None:
    exact = f"IGITools-setup-{version}.exe".lower()
    candidates = [
        a
        for a in assets
        if isinstance(a, dict)
        and INSTALLER_NAME_RE.match(str(a.get("name") or ""))
        and a.get("browser_download_url")
    ]
    if not candidates:
        return None
    for asset in candidates:
        if str(asset.get("name", "")).lower() == exact:
            return asset
    return candidates[0]


def fetch_latest_release() -> ReleaseInfo | None:
    data = _http_get_json(RELEASES_API)
    tag = str(data.get("tag_name") or "").strip()
    version = tag.lstrip("vV")
    if not version:
        return None
    asset = _pick_installer_asset(list(data.get("assets") or []), version)
    if asset is None:
        return None
    return ReleaseInfo(
        version=version,
        tag=tag,
        download_url=str(asset["browser_download_url"]),
        asset_name=str(asset.get("name") or "IGITools-setup.exe"),
        size=int(asset.get("size") or 0),
        notes=str(data.get("body") or "").strip(),
    )


def check_for_update() -> ReleaseInfo | None:
    local = get_installed_version()
    remote = fetch_latest_release()
    if remote is None or not is_newer(remote.version, local):
        return None
    return remote


def _format_size(num: int) -> str:
    if num <= 0:
        return "?"
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if num < 1024 or unit == "ГБ":
            if unit == "Б":
                return f"{num} {unit}"
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} ГБ"


def _format_release_notes(notes: str, *, max_chars: int = 1200) -> str:
    """Упростить markdown из GitHub Release body для MessageBox."""
    text = (notes or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""

    lines: list[str] = []
    for raw in text.split("\n"):
        line = raw.rstrip()
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[-*+]\s+", "• ", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"__(.+?)__", r"\1", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        lines.append(line)

    cleaned = "\n".join(lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    if len(cleaned) > max_chars:
        cut = cleaned[: max_chars - 1].rsplit("\n", 1)[0].rstrip()
        if not cut:
            cut = cleaned[: max_chars - 1].rstrip()
        cleaned = cut + "…"
    return cleaned


def _acquire_ui() -> None:
    global _resource_override
    if _resource_override is None:
        from pyrx import Ap

        _resource_override = Ap.ResourceOverride()


def _release_ui() -> None:
    global _resource_override
    _resource_override = None


def _shell_open(url: str) -> None:
    """Открыть URL/файл системным обработчиком (вне процесса CAD)."""
    import ctypes

    rc = ctypes.windll.shell32.ShellExecuteW(None, "open", url, None, None, 1)
    if rc <= 32:
        raise RuntimeError(f"ShellExecute не удалось (код {rc})")


def _offer_update_ui(info: ReleaseInfo) -> None:
    global _declined_this_session
    import wx

    _acquire_ui()
    try:
        local = get_installed_version()
        size_txt = _format_size(info.size)
        notes = _format_release_notes(info.notes)
        message = (
            f"Доступна новая версия IGI Tools.\n\n"
            f"Установлена: {local}\n"
            f"Актуальная:  {info.version}\n"
            f"Размер:      {size_txt}"
        )
        if notes:
            message += f"\n\nЧто нового:\n{notes}"
        message += (
            "\n\nОткрыть скачивание установщика в браузере?"
        )

        answer = wx.MessageBox(
            message,
            "IGI Tools — обновление",
            wx.YES_NO | wx.ICON_INFORMATION,
        )
        if answer != wx.YES:
            _declined_this_session = True
            print(f"[IGI Tools] Обновление до {info.version} отложено.")
            return

        try:
            _shell_open(info.download_url)
        except Exception as exc:
            # Запасной путь — страница релизов
            try:
                _shell_open(RELEASES_PAGE)
            except Exception:
                wx.MessageBox(
                    f"Не удалось открыть ссылку на установщик.\n\n"
                    f"{exc}\n\n"
                    f"Скачайте вручную:\n{info.download_url}",
                    "IGI Tools — ошибка",
                    wx.OK | wx.ICON_ERROR,
                )
                print(f"[IGI Tools] Не удалось открыть загрузку: {exc}")
                return

        wx.MessageBox(
            f"Скачивание «{info.asset_name}» запущено в браузере.\n\n"
            "Перед установкой закройте AutoCAD / Civil 3D, "
            "затем запустите скачанный установщик от имени администратора.\n\n"
            f"Если загрузка не началась:\n{RELEASES_PAGE}",
            "IGI Tools — обновление",
            wx.OK | wx.ICON_INFORMATION,
        )
        print(
            f"[IGI Tools] Открыта загрузка {info.version}: {info.download_url}"
        )
    finally:
        _release_ui()


def _run_update_check(*, silent_if_current: bool) -> None:
    """Фоновая проверка; UI — через wx.CallAfter."""

    def worker() -> None:
        try:
            local = get_installed_version()
            print(f"[IGI Tools] Проверка обновлений (установлено {local})…")
            info = check_for_update()
            if info is None:
                msg = f"[IGI Tools] Версия актуальна ({local})."
                print(msg)
                if not silent_if_current:
                    import wx

                    def _show_current() -> None:
                        _acquire_ui()
                        try:
                            wx.MessageBox(
                                f"Установлена актуальная версия IGI Tools:\n{local}",
                                "IGI Tools — обновление",
                                wx.OK | wx.ICON_INFORMATION,
                            )
                        finally:
                            _release_ui()

                    wx.CallAfter(_show_current)
                return
            print(f"[IGI Tools] Доступно обновление: {local} → {info.version}")
            import wx

            wx.CallAfter(_offer_update_ui, info)
        except urllib.error.HTTPError as exc:
            detail = (
                "Релизы на GitHub пока недоступны (404)."
                if exc.code == 404
                else f"HTTP {exc.code}"
            )
            print(f"[IGI Tools] Проверка обновлений: {detail}")
            if not silent_if_current:
                import wx

                def _show_http_err() -> None:
                    _acquire_ui()
                    try:
                        wx.MessageBox(
                            f"Не удалось проверить обновления:\n{detail}",
                            "IGI Tools — обновление",
                            wx.OK | wx.ICON_WARNING,
                        )
                    finally:
                        _release_ui()

                wx.CallAfter(_show_http_err)
        except Exception as exc:
            print(f"[IGI Tools] Проверка обновлений: {exc}")
            if not silent_if_current:
                import wx

                def _show_err() -> None:
                    _acquire_ui()
                    try:
                        wx.MessageBox(
                            f"Не удалось проверить обновления:\n{exc}",
                            "IGI Tools — обновление",
                            wx.OK | wx.ICON_WARNING,
                        )
                    finally:
                        _release_ui()

                wx.CallAfter(_show_err)

    threading.Thread(
        target=worker, daemon=True, name="igi-update-check"
    ).start()


def schedule_update_check() -> None:
    """Автопроверка при старте (с задержкой, без диалога если всё актуально)."""
    global _check_started
    if _check_started or _declined_this_session:
        return
    _check_started = True

    def start_worker() -> None:
        _run_update_check(silent_if_current=True)

    try:
        import wx

        wx.CallLater(2500, start_worker)
    except Exception:
        start_worker()


def check_update_interactive() -> None:
    """Ручная проверка (команда CAD): всегда показывает результат."""
    global _declined_this_session
    _declined_this_session = False
    _run_update_check(silent_if_current=False)
