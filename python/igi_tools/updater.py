"""Проверка обновлений IGI Tools через GitHub Releases."""

from __future__ import annotations

import json
import re
import ssl
import tempfile
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree as ET

GITHUB_OWNER = "maxmyslivets"
GITHUB_REPO = "IGI-Tools"
RELEASES_API = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
INSTALLER_NAME_RE = re.compile(r"^IGITools-setup-.*\.exe$", re.IGNORECASE)
CAD_PROCESS_NAMES = frozenset({"acad.exe", "accoreconsole.exe"})
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


def download_installer(
    info: ReleaseInfo,
    dest: Path,
    on_progress: Callable[[int, int], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> Path:
    """Скачать установщик. on_progress(downloaded, total)."""
    req = urllib.request.Request(
        info.download_url,
        headers={"User-Agent": USER_AGENT},
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
        total = int(resp.headers.get("Content-Length") or info.size or 0)
        downloaded = 0
        chunk_size = 256 * 1024
        with open(dest, "wb") as out:
            while True:
                if should_cancel and should_cancel():
                    raise RuntimeError("Скачивание отменено")
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if on_progress:
                    on_progress(downloaded, total)
    return dest


def _cad_processes_running() -> list[str]:
    """Имена запущенных процессов AutoCAD / Civil (acad.exe и т.п.)."""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        TH32CS_SNAPPROCESS = 0x00000002

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == ctypes.c_void_p(-1).value:
            return []
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            found: list[str] = []
            if kernel32.Process32FirstW(snap, ctypes.byref(entry)):
                while True:
                    name = entry.szExeFile.lower()
                    if name in CAD_PROCESS_NAMES:
                        found.append(entry.szExeFile)
                    if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                        break
            return found
        finally:
            kernel32.CloseHandle(snap)
    except Exception:
        return []


def _launch_installer(path: Path) -> None:
    import ctypes

    rc = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        str(path),
        None,
        str(path.parent),
        1,
    )
    if rc <= 32:
        raise RuntimeError(f"Не удалось запустить установщик (код {rc})")


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
        # headings / list markers
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[-*+]\s+", "• ", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        # bold/italic/code
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"__(.+?)__", r"\1", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        # links: [label](url) → label
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        lines.append(line)

    cleaned = "\n".join(lines).strip()
    # collapse 3+ blank lines
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
        message += "\n\nСкачать и установить обновление?"

        answer = wx.MessageBox(
            message,
            "IGI Tools — обновление",
            wx.YES_NO | wx.ICON_INFORMATION,
        )
        if answer != wx.YES:
            _declined_this_session = True
            print(f"[IGI Tools] Обновление до {info.version} отложено.")
            _release_ui()
            return

        dest = Path(tempfile.gettempdir()) / info.asset_name
        cancelled = {"flag": False}
        dlg = wx.ProgressDialog(
            "IGI Tools — скачивание",
            f"Скачивание {info.asset_name}…" + (" " * 40),
            maximum=100,
            parent=None,
            style=wx.PD_APP_MODAL
            | wx.PD_AUTO_HIDE
            | wx.PD_CAN_ABORT
            | wx.PD_ELAPSED_TIME
            | wx.PD_ESTIMATED_TIME
            | wx.PD_REMAINING_TIME,
        )

        def on_progress(downloaded: int, total: int) -> None:
            def update() -> None:
                if cancelled["flag"]:
                    return
                if total > 0:
                    percent = min(99, int(downloaded * 100 / total))
                    msg = (
                        f"{_format_size(downloaded)} / {_format_size(total)} — "
                        f"{info.asset_name}"
                    )
                else:
                    percent = min(99, (dlg.GetValue() + 1) % 100)
                    msg = f"{_format_size(downloaded)} — {info.asset_name}"
                cont, _skip = dlg.Update(percent, msg)
                if not cont:
                    cancelled["flag"] = True

            wx.CallAfter(update)

        def worker() -> None:
            try:
                download_installer(
                    info,
                    dest,
                    on_progress=on_progress,
                    should_cancel=lambda: cancelled["flag"],
                )
                wx.CallAfter(_on_download_finished, dlg, dest, cancelled)
            except Exception as exc:
                wx.CallAfter(_on_download_failed, dlg, cancelled, exc)

        threading.Thread(target=worker, daemon=True).start()
    except Exception:
        _release_ui()
        raise


def _on_download_failed(
    dlg: object, cancelled: dict, exc: BaseException
) -> None:
    import wx

    try:
        if hasattr(dlg, "Destroy"):
            dlg.Destroy()  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        if cancelled.get("flag"):
            print("[IGI Tools] Скачивание обновления отменено.")
            return
        wx.MessageBox(
            f"Не удалось скачать обновление:\n{exc}",
            "IGI Tools — ошибка",
            wx.OK | wx.ICON_ERROR,
        )
        print(f"[IGI Tools] Ошибка обновления: {exc}")
    finally:
        _release_ui()


def _on_download_finished(dlg: object, dest: Path, cancelled: dict) -> None:
    import wx

    try:
        if not cancelled.get("flag") and hasattr(dlg, "Update"):
            dlg.Update(100, "Готово")  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        if hasattr(dlg, "Destroy"):
            dlg.Destroy()  # type: ignore[attr-defined]
    except Exception:
        pass

    try:
        if cancelled.get("flag"):
            try:
                dest.unlink(missing_ok=True)
            except OSError:
                pass
            print("[IGI Tools] Скачивание обновления отменено.")
            return

        if not dest.is_file():
            wx.MessageBox(
                "Файл установщика не найден после скачивания.",
                "IGI Tools — ошибка",
                wx.OK | wx.ICON_ERROR,
            )
            return

        running = _cad_processes_running()
        warn = (
            "Скачивание завершено.\n\n"
            "Перед установкой закройте AutoCAD / Civil 3D — "
            "иначе файлы плагина могут быть заняты и установка завершится с ошибкой.\n\n"
        )
        if running:
            names = ", ".join(sorted(set(running)))
            warn += f"Сейчас обнаружены процессы CAD: {names}\n\n"
        warn += (
            "Закройте все сеансы AutoCAD / Civil 3D, "
            "затем нажмите «Да», чтобы запустить установщик."
        )

        if (
            wx.MessageBox(
                warn,
                "IGI Tools — перед установкой",
                wx.YES_NO | wx.ICON_WARNING,
            )
            != wx.YES
        ):
            print(f"[IGI Tools] Установщик сохранён: {dest}")
            wx.MessageBox(
                f"Установщик сохранён:\n{dest}\n\n"
                "Запустите его вручную после закрытия CAD.",
                "IGI Tools",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        still = _cad_processes_running()
        if still:
            if (
                wx.MessageBox(
                    "AutoCAD / Civil 3D всё ещё запущен.\n\n"
                    "Запустить установщик всё равно?\n"
                    "(рекомендуется сначала закрыть CAD)",
                    "IGI Tools — предупреждение",
                    wx.YES_NO | wx.ICON_WARNING,
                )
                != wx.YES
            ):
                print(f"[IGI Tools] Установщик сохранён: {dest}")
                return

        try:
            _launch_installer(dest)
            print(f"[IGI Tools] Запущен установщик: {dest}")
            wx.MessageBox(
                "Установщик запущен.\n\n"
                "После установки перезапустите AutoCAD / Civil 3D.",
                "IGI Tools",
                wx.OK | wx.ICON_INFORMATION,
            )
        except Exception as exc:
            wx.MessageBox(
                f"Не удалось запустить установщик:\n{exc}\n\nФайл:\n{dest}",
                "IGI Tools — ошибка",
                wx.OK | wx.ICON_ERROR,
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
