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

import wx  # noqa: E402 — CADPyRx bundle гарантирует наличие wxPython
import wx.html  # noqa: E402 — HtmlWindow для рендеринга release notes

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

_SETTINGS_DIR = Path.home() / ".igi-tools"
_SETTINGS_FILE = _SETTINGS_DIR / "updater_settings.json"

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


def _ssl_context() -> ssl.SSLContext:
    """SSL-контекст для HTTPS из embedded Python (часто без CA bundle)."""
    ctx = ssl.create_default_context()

    try:
        import certifi

        ctx.load_verify_locations(certifi.where())
        return ctx
    except ImportError:
        pass

    here = Path(__file__).resolve()
    for base in (here.parents[2], here.parents[3]):
        pem = (
            base
            / "runtime"
            / "Lib"
            / "site-packages"
            / "certifi"
            / "cacert.pem"
        )
        if pem.is_file():
            ctx.load_verify_locations(str(pem))
            return ctx

    if hasattr(ctx, "load_default_certs"):
        try:
            ctx.load_default_certs()
        except ssl.SSLError:
            pass

    return ctx


def _http_get_json(url: str, timeout: float = 15.0) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    ctx = _ssl_context()
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


def _markdown_to_html(text: str) -> str:
    """Конвертировать markdown в HTML для wx.html.HtmlWindow."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    # Вырезать HTML-картинки и picture-блоки
    text = re.sub(r"<picture[^>]*>.*?</picture>", "", text, flags=re.DOTALL)
    text = re.sub(r"<img[^>]*/?>", "", text, flags=re.DOTALL)
    if not text.strip():
        return ""

    lines = text.split("\n")
    html_parts: list[str] = []
    in_code_block = False
    code_buf: list[str] = []
    in_list = False

    def _close_list() -> None:
        nonlocal in_list
        if in_list:
            html_parts.append("</ul>")
            in_list = False

    def _inline(line: str) -> str:
        # Картинки (![alt](url)) удаляем полностью — не загружаем
        line = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
        line = re.sub(r"__(.+?)__", r"<b>\1</b>", line)
        line = re.sub(r"(?<![*])\*(?![*])(.+?)(?<![*])\*(?![*])", r"<i>\1</i>", line)
        line = re.sub(r"_(.+?)_", r"<i>\1</i>", line)
        line = re.sub(r"`([^`]+)`", r"<code>\1</code>", line)
        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', line)
        return line

    for raw in lines:
        line = raw.rstrip()

        if line.startswith("```"):
            if in_code_block:
                html_parts.append(
                    "<pre><code>"
                    + _escape_html("\n".join(code_buf))
                    + "</code></pre>"
                )
                code_buf.clear()
                in_code_block = False
            else:
                _close_list()
                in_code_block = True
            continue

        if in_code_block:
            code_buf.append(line)
            continue

        if not line:
            _close_list()
            html_parts.append("<br>")
            continue

        h_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if h_match:
            _close_list()
            level = len(h_match.group(1))
            html_parts.append(f"<h{level}>{_inline(h_match.group(2))}</h{level}>")
            continue

        li_match = re.match(r"^[-*+]\s+(.+)$", line)
        if li_match:
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"<li>{_inline(li_match.group(1))}</li>")
            continue

        ol_match = re.match(r"^\d+\.\s+(.+)$", line)
        if ol_match:
            if not in_list:
                html_parts.append("<ol>")
                in_list = True
            html_parts.append(f"<li>{_inline(ol_match.group(1))}</li>")
            continue

        _close_list()
        html_parts.append(f"<p>{_inline(line)}</p>")

    _close_list()
    if in_code_block and code_buf:
        html_parts.append(
            "<pre><code>" + _escape_html("\n".join(code_buf)) + "</code></pre>"
        )

    body = "\n".join(html_parts)
    return (
        "<html><body style='"
        "font-family:Segoe UI,sans-serif;font-size:9pt;"
        "color:WindowText;background-color:Window;"
        "padding:4px;margin:0;"
        "'>"
        "<style>"
        "pre{white-space:pre-wrap;word-wrap:break-word;overflow-wrap:break-word;}"
        "code{white-space:pre-wrap;word-wrap:break-word;}"
        "p,li{word-wrap:break-word;overflow-wrap:break-word;}"
        "</style>"
        f"{body}"
        "</body></html>"
    )


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


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


# ─── Персистентные настройки (отложенные версии) ─────────────────────


def _load_settings() -> dict:
    try:
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_settings(data: dict) -> None:
    try:
        _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[IGI Tools] Настройки сохранены: {_SETTINGS_FILE}")
    except Exception as exc:
        print(f"[IGI Tools] Не удалось сохранить настройки {_SETTINGS_FILE}: {exc}")


def _postpone_version(version: str) -> None:
    """Запомнить версию, на которую больше не показывать запрос."""
    data = _load_settings()
    data["postponed_version"] = version
    _save_settings(data)
    print(f"[IGI Tools] Версия {version} отложена до следующего обновления.")


def _is_version_postponed(version: str) -> bool:
    """Показывать запрос на эту версию?"""
    data = _load_settings()
    saved = data.get("postponed_version", "")
    return bool(saved) and not is_newer(version, saved)


# ─── UI диалог обновления ───────────────────────────────────────────


class _UpdateDialog(wx.Dialog):
    """Кастомный диалог с тремя кнопками: Скачать / Отложить / Позже."""

    POSTPONE = wx.NewIdRef()

    def __init__(self, info: ReleaseInfo, parent=None):
        wx.Dialog.__init__(
            self,
            parent,
            title="IGI Tools — обновление",
            style=(
                wx.DEFAULT_DIALOG_STYLE
                | wx.RESIZE_BORDER
                | wx.MAXIMIZE_BOX
                | wx.STAY_ON_TOP
            ),
        )
        self.SetMinSize(wx.Size(520, 420))

        self._base_html = _markdown_to_html(info.notes)
        self._html: wx.html.HtmlWindow | None = None

        local = get_installed_version()
        size_txt = _format_size(info.size)

        panel = wx.Panel(self)
        vsizer = wx.BoxSizer(wx.VERTICAL)

        # Заголовок
        title = wx.StaticText(
            panel, label="Доступна новая версия IGI Tools"
        )
        title.SetFont(
            wx.Font(
                11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD
            )
        )
        vsizer.Add(title, flag=wx.BOTTOM, border=12)

        # Информация о версиях
        info_text = wx.StaticText(
            panel,
            label=(
                f"Установлена: {local}\n"
                f"Актуальная:  {info.version}\n"
                f"Размер:      {size_txt}"
            ),
        )
        vsizer.Add(info_text, flag=wx.BOTTOM, border=8)

        # Что нового — HtmlWindow
        if self._base_html:
            vsizer.Add(
                wx.StaticText(panel, label="Что нового:"),
                flag=wx.BOTTOM, border=4,
            )
            self._html = wx.html.HtmlWindow(
                panel,
                style=wx.html.HW_SCROLLBAR_AUTO,
            )
            self._html.SetBorders(2)
            self._html.SetHTMLBackgroundColour(
                wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
            )
            self._html.SetPage(self._base_html)
            vsizer.Add(
                self._html, proportion=1, flag=wx.EXPAND | wx.BOTTOM, border=12
            )
        else:
            vsizer.AddStretchSpacer(1)

        # Кнопки
        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        download_btn = wx.Button(panel, wx.ID_OK, label="Скачать")
        postpone_btn = wx.Button(panel, self.POSTPONE, label="Отложить до следующего обновления")
        postpone_btn.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(self.POSTPONE))
        later_btn = wx.Button(panel, wx.ID_CANCEL, label="Напомнить позже")

        btn_row.Add(download_btn, flag=wx.RIGHT, border=8)
        btn_row.Add(postpone_btn, flag=wx.RIGHT, border=8)
        btn_row.Add(later_btn)

        vsizer.Add(btn_row, flag=wx.ALIGN_CENTER)

        panel.SetSizerAndFit(vsizer)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, proportion=1, flag=wx.EXPAND | wx.ALL, border=12)
        self.SetSizerAndFit(outer)
        self.SetSize(wx.Size(640, 560))


def _offer_update_ui(info: ReleaseInfo) -> None:
    global _declined_this_session

    _acquire_ui()
    try:
        dlg = _UpdateDialog(info)
        answer = dlg.ShowModal()

        if answer == wx.ID_OK:
            # Скачать
            dlg.Destroy()
            try:
                _shell_open(info.download_url)
            except Exception as exc:
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
        elif answer == _UpdateDialog.POSTPONE:
            # Отложить до следующего обновления — запомнить версию
            _postpone_version(info.version)
            dlg.Destroy()
            return
        else:
            # Напомнить позже (в этом сеансе)
            dlg.Destroy()
            _declined_this_session = True
            print(f"[IGI Tools] Обновление до {info.version} отложено.")
            return
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
            err_text = str(exc)
            if isinstance(exc, urllib.error.URLError) and "CERTIFICATE_VERIFY_FAILED" in err_text:
                err_text = (
                    f"{err_text}\n\n"
                    "Не удалось проверить сертификат HTTPS (типично для "
                    "python-embed без пакета certifi).\n"
                    "Для разработчиков: pip install certifi в python-embed "
                    "и пересоберите bundle."
                )
            print(f"[IGI Tools] Проверка обновлений: {err_text}")
            if not silent_if_current:
                import wx

                def _show_err(message: str = err_text) -> None:
                    _acquire_ui()
                    try:
                        wx.MessageBox(
                            f"Не удалось проверить обновления:\n{message}",
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
        info = check_for_update()
        if info is not None and _is_version_postponed(info.version):
            print(
                f"[IGI Tools] Версия {info.version} отложена пользователем "
                "— автопроверка пропущена."
            )
            return
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
