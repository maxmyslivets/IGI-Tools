# AGENTS.md — руководство для контрибьютеров IGI-Tools

Плагин для **AutoCAD / Civil 3D** (2022–2027) на стеке: AutoLISP + [CADPyRx](https://github.com/CEXT-Dan/PyRx) + опционально wxPython / CUIX.

---

## Структура проекта и организация модулей

```
IGI-Tools/
├── VERSION                     # semver (MAJOR.MINOR.PATCH) — источник правды
├── Makefile                    # обёртка над PowerShell-скриптами
├── lisp/                       # исходники AutoLISP (UTF-8)
├── python/
│   ├── pyrx_onload.py          # точка входа: добавляет sys.path, импортирует команды
│   └── igi_tools/
│       ├── __init__.py         # __version__ = _read_version()
│       ├── paths.py            # пути к файлам плагина
│       ├── updater.py          # проверка обновлений через GitHub API
│       └── commands/
│           ├── __init__.py     # __all__ — регистрация команд
│           ├── buffer_poly.py  # (новый модуль)
│           ├── check_update.py
│           ├── dem_tracker.py
│           ├── draw_nomenclature.py
│           ├── fill_area.py
│           ├── gzu_from_geojson.py
│           ├── manage_template.py
│           └── reload_all.py
├── bundle/                     # шаблон PackageContents + IGIToolsLoader.lsp
├── ui/igi_tools.cuix           # настраиваемая панель инструментов AutoCAD
├── scripts/                    # build-bundle, deploy-dev, build-installer, Version
├── installer/IGITools-setup.iss # Inno Setup
├── resources/template.dwg      # DWG-шаблон с блоками/слоями/типами линий
└── python-embed/               # локальный runtime (gitignore, ~1ГБ)
```

При старте CAD: `PackageContents.xml` → RxLoader → `pyrx_onload.py` → импорт `igi_tools.commands`.

---

## Команды сборки, тестирования и разработки

Установите **GNU Make** (Git for Windows, `scoop install make` или `choco install make`).

| Команда | Назначение |
|---------|------------|
| `make deploy` | Полная сборка + установка в `ApplicationPlugins` (admin) |
| `make deploy-fast` | Без копирования runtime (только код/ресурсы) |
| `make deploy-junction` | `mklink /J` на `dist/IGITools.bundle` (мгновенное обновление) |
| `make bundle` | Сборка `dist/IGITools.bundle` |
| `make bundle-fast` | Сборка без `Contents/runtime` |
| `make installer` | Bundle + Inno Setup EXE |
| `make version` | Показать текущую версию |
| `make clean` | Удалить `dist/` |

Проброс аргументов: `make deploy-fast ARGS="-NoBump"` или `make bundle Version=minor`.

Типичный dev-цикл:
1. `make deploy-junction` (один раз).
2. Правите код в `python/` или `lisp/`.
3. `make deploy-fast ARGS="-NoBump"`.
4. В AutoCAD: `IGI_RELOAD_ALL` (для Python) или перезапуск CAD.

**Важно:** AutoCAD должен быть закрыт при deploy — DLL/PYD блокируются процессом.

---

## Стиль кода и правила именования

### Python

- Все файлы: `from __future__ import annotations` — обязательно первой строкой кода.
- Команды регистрируются через декоратор `@command(name="IGI_НАЗВАНИЕ")` из `pyrx`.
- Тело команды — функция с аннотацией `-> None`.
- Вывод в консоль CAD — обычный `print()`.
- Имена файлов: snake_case (например `draw_nomenclature.py`).
- Кодировка: UTF-8.

### Создание нового Python-инструмента (команды)

Ниже — всё, что нужно знать, чтобы написать новую команду, не заглядывая в существующий код.

#### 1. Полный шаблон файла команды

Создайте `python/igi_tools/commands/my_tool.py`:

```python
"""Краткое описание: что делает команда, какие объекты создаёт."""

from __future__ import annotations

import traceback

from pyrx import Db, Ed, Ge, command

# Константы настройки — в верхний уровень модуля
MY_CONSTANT = 42.0


@command(name="IGI_MY_TOOL")
def my_tool() -> None:
    """Однострочное описание для справки."""
    print("\n[IGI Tools] Запуск IGI_MY_TOOL…")

    try:
        # --- 1. Запрос ввода от пользователя ---
        # --- 2. Основная логика ---
        # --- 3. Создание/изменение объектов ---
        pass
    except Exception:
        traceback.print_exc()
        print("[IGI Tools] Ошибка: команда прервана.")
```

Обязательно:
- `from __future__ import annotations` — первой строкой кода.
- `@command(name="IGI_НАЗВАНИЕ")` — имя команды для AutoCAD (префикс `IGI_`).
- Возвращаемый тип `-> None`.
- Вывод в консоль CAD — `print()`.
- Всё тело — в `try/except` с `traceback.print_exc()`.

#### 2. Регистрация в `__init__.py`

Добавьте в `python/igi_tools/commands/__init__.py`:

```python
from igi_tools.commands import my_tool as _my_tool  # noqa: F401

__all__ = [
    ...,
    "my_tool",
]
```

После deploy и `IGI_RELOAD_ALL` команда станет доступна.

#### 3. Взаимодействие с пользователем в AutoCAD

Импорт: `from pyrx import Ed`

| Действие | Код |
|----------|------|
| Выбрать 1 объект | `result, oid = Ed.Editor.entSel("\nВыберите полилинию: ")` — возвращает `Ed.Result` и `Db.ObjectId` |
| Указать точку | `result, point = Ed.Editor.getPoint("\nУкажите точку: ")` — `point` = `Ge.Point3d` |
| Ввести число | `result, val = Ed.Editor.getReal("\nВведите шаг: ")` — `val` = `float` |
| Ввести текст | `result, val = Ed.Editor.getString("\nВведите имя слоя: ")` — `val` = `str` |
| Выбрать несколько | `result, ids = Ed.Editor.select("\nВыберите объекты: ")` — `ids` = `[Db.ObjectId, ...]` |
| Диалог выбора DWG | `path = Ed.Core.getFileD("Заголовок", "", "dwg", 0)` — строка пути или `""` |

Каждый возвращает `Ed.Result` — проверяйте `result == Ed.Result.eOk`.

Пример:
```python
res, oid = Ed.Editor.entSel("\nВыберите полилинию: ")
if res != Ed.Result.eOk:
    print("[IGI Tools] Выбор отменён.")
    return
```

#### 4. Работа с БД чертежа (создание/чтение объектов)

Импорт: `from pyrx import Db, Ge`

**Открыть объект на чтение:**
```python
pline = Db.Polyline(oid, Db.OpenMode.kForRead)
```

**Открыть на запись (через `upgradeOpen`):**
```python
pline.upgradeOpen()
pline.setColor(3)  # зелёный
pline.downgradeOpen()
```

**Создать новый объект — всегда через `Db.Transaction` или вручную в `CurrentSpace`:**
```python
db = Db.curDb()
model = Db.BlockTableRecord(db.getModelSpaceId(), Db.OpenMode.kForWrite)

# Полилиния
pts = [Ge.Point3d(0,0,0), Ge.Point3d(10,0,0), Ge.Point3d(10,10,0)]
pline = Db.Polyline(len(pts))
for i, p in enumerate(pts):
    pline.addVertexAt(i, Ge.Point2d(p.x, p.y))
pline.setClosed()
pline.setColor(3)
model.append(pline)

# Линия
line = Db.Line(Ge.Point3d(0,0,0), Ge.Point3d(100,0,0))
line.setColor(1)
model.append(line)

# Текст (DText)
text = Db.Text()
text.setText("Пример")
text.setPosition(Ge.Point3d(50, 50, 0))
text.setHeight(10.0)
model.append(text)

model.close()
```

**Чтение образца (блока) из template.dwg:**
```python
from igi_tools.paths import get_template_path

# Открыть template.dwg как внешнюю БД
src_db = Db.Database(False, True)
src_db.readDwgFile(str(get_template_path()))

# Искать блок по имени
bt = Db.BlockTable(src_db.getBlockTableId(), Db.OpenMode.kForRead)
if bt.has(BLOCK_NAME):
    btr_id = bt.get(BLOCK_NAME)
    # Клонировать определение блока и все зависимости
    id_map = Db.IdMapping()
    wblock_clone = src_db.wblock(btr_id, id_map)
    cur_db = Db.curDb()
    id_map2 = Db.IdMapping()
    cur_db.insert(btr_id, wblock_clone, id_map2, False)
bt.close()

# Вставить блок-ссылку
btr_id = ...  # полученный после insert
bref = Db.BlockReference(Ge.Point3d(x, y, 0), btr_id)
bref.setColor(3)
bref.setScaleFactors(Ge.Scale3d(0.5, 0.5, 0.5))
model.append(bref)
```

**Вершины полилинии:**
```python
pts = []
for i in range(pline.numVerts()):
    p = pline.getPointAtParam(float(i))
    pts.append((p.x, p.y))
```

**Проверка замкнутости:** `pline.isClosed()`

#### 5. wxPython UI (диалог настроек)

Для команд с настройками используйте wx.Dialog (фреймворк уже встроен в CADPyRx):

```python
import wx

class _MyDialog(wx.Dialog):
    def __init__(self, parent=None):
        wx.Dialog.__init__(self, parent, title="Мой инструмент — Параметры",
                           style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        self.SetMinSize(wx.Size(380, 300))
        self.result_data: dict | None = None

        panel = wx.Panel(self)
        vsizer = wx.BoxSizer(wx.VERTICAL)

        # Поле ввода
        vsizer.Add(wx.StaticText(panel, label="Интервал:"),
                   flag=wx.BOTTOM, border=4)
        self.step_ctrl = wx.TextCtrl(panel, value="10.0")
        vsizer.Add(self.step_ctrl, flag=wx.EXPAND | wx.BOTTOM, border=12)

        # Checkbox
        self.chk = wx.CheckBox(panel, label="Создать контур")
        self.chk.SetValue(True)
        vsizer.Add(self.chk, flag=wx.BOTTOM, border=12)

        # Кнопки OK / Отмена
        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        ok_btn = wx.Button(panel, wx.ID_OK, label="Выполнить")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="Отмена")
        btn_row.Add(ok_btn, flag=wx.RIGHT, border=8)
        btn_row.Add(cancel_btn)
        vsizer.Add(btn_row, flag=wx.ALIGN_CENTER)

        panel.SetSizer(vsizer)
        vsizer.Fit(panel)
        self.Fit()


def _show_dialog() -> dict | None:
    dlg = _MyDialog()
    if dlg.ShowModal() == wx.ID_OK:
        data = {
            "step": float(dlg.step_ctrl.GetValue()),
            "create_boundary": dlg.chk.GetValue(),
        }
        dlg.Destroy()
        return data
    dlg.Destroy()
    return None
```

wx вызывается синхронно — `ShowModal()` блокирует команду до закрытия диалога.

#### 6. Сохранение/загрузка настроек (JSON persistence)

Настройки храните в `get_resources_dir()` — между сессиями AutoCAD:

```python
import json
from pathlib import Path
from igi_tools.paths import get_resources_dir

SETTINGS_FILE = get_resources_dir() / "my_tool_settings.json"


def _load_settings() -> dict:
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_settings(data: dict) -> None:
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # настройки — некритично
```

Для настроек, которые не должны сбрасываться при переустановке, используйте `%APPDATA%/IGI-Tools/my_tool_settings.json` (см. `dem_tracker.py`).

#### 7. Обработка ошибок и проверка результата

- Всегда оборачивайте тело команды в `try/except` + `traceback.print_exc()`.
- Проверяйте результат выбора: `if res != Ed.Result.eOk: return`.
- Для проверки существования файла: `Path("…").is_file()`.
- Для комбинированного выбора/отмены (пользователь нажал Esc): проверяйте `result`.
- Для отмены через wx: проверяйте `ShowModal() == wx.ID_OK`.

#### 8. Проверка в AutoCAD

1. `make deploy-fast ARGS="-NoBump"`
2. В AutoCAD: `IGI_RELOAD_ALL`
3. `IGI_MY_TOOL`
4. Если произошла ошибка — смотрите текст в командной строке AutoCAD (там будет Python traceback).
5. Для отладки — `print()` промежуточных значений в консоль CAD.

### AutoLISP

- Исходники в `lisp/` хранятся в **UTF-8**.
- Сборка конвертирует в **Windows-1251** (кириллица в `princ` / `alert`).
- Команды: `(defun c:НАЗВАНИЕ ...)`.

### CUIX

Редактируйте через AutoCAD (команда `CUI`), сохраняйте как partial customization в `ui/igi_tools.cuix`.

---

## Рекомендации по VCS: коммиты и пулл реквесты

### Коммиты

История ведётся на **русском языке**, в свободной описательной форме. Примеры:

```
3.3.0
Исправлена подсказка в UI для кнопки "Построение номенклатуры"
добавлена проверка величины промера (|x|<20м) ...
Переделана заливка блоками - добавлен gui - добавлена память
```

- Первая строка — версия (тег), если это релизный коммит, иначе краткое описание изменения.
- Допустимы многострочные сообщения.
- Файл `VERSION` меняется скриптами сборки; коммитить его при релизе.

### PR

- Название и описание — на русском.
- Приложите скриншоты результата в AutoCAD, если изменение визуальное.
- Если это новая команда — опишите её синтаксис и поведение.

---

## Архитектурные заметки

- **Не используйте** `pyautocad`, `pythonnet` или .NET ObjectARX-обёртки — только CADPyRx.
- **Путь установки** — `%ProgramFiles%\Autodesk\ApplicationPlugins` (не `ProgramData`; с AutoCAD 2026 ProgramData ограничен).
- **Версии CAD → RxLoader**: 2022→R24.1, 2023→R24.2, 2024→R24.3, 2025→R25.0, 2026→R25.1, 2027→R26.0.
- Документация API: https://cext-dan.github.io/CADPyRxDoc/
- Примеры: https://github.com/CEXT-Dan/PyRx/tree/main/PySamples