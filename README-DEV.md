# IGI Tools — руководство разработчика

Стек: **Autodesk ApplicationPlugins bundle** + **AutoLISP** + **CADPyRx** (ObjectARX Python) + опционально **wxPython** / **CUIX**.

## Архитектура

```text
IGITools.bundle/
  PackageContents.xml          # автозагрузка RxLoader / LISP / CUIX
  Contents/
    runtime/                   # python-embed + site-packages (cad-pyrx)
    Lisp/                      # *.lsp, *.vlx + IGIToolsLoader.lsp
    Python/                    # pyrx_onload.py + пакет igi_tools
    Resources/igi_tools.cuix
```

При старте CAD:

1. `PackageContents.xml` грузит версионный `RxLoaderXX.arx` и `IGIToolsLoader.lsp` / CUIX.
2. RxLoader поднимает встроенный Python CADPyRx и ищет `pyrx_onload.py` (через `SupportPath`).
3. `pyrx_onload.py` добавляет `Contents/Python` в `sys.path` и импортирует команды.
4. LISP-загрузчик подхватывает все `*.lsp` / `*.vlx` из `Contents/Lisp`.

Маппинг версий CAD → RxLoader:

| CAD | Series | RxLoader |
|-----|--------|----------|
| 2022 | R24.1 | RxLoader24.1.arx |
| 2023 | R24.2 | RxLoader24.2.arx |
| 2024 | R24.3 | RxLoader24.3.arx |
| 2025 | R25.0 | RxLoader25.0.arx |
| 2026 | R25.1 | RxLoader25.1.arx |
| 2027 | R26.0 | RxLoader26.0.arx |

Документация API: https://cext-dan.github.io/CADPyRxDoc/  
Примеры: https://github.com/CEXT-Dan/PyRx/tree/main/PySamples

## Структура репозитория

```text
VERSION               текущая semver (MAJOR.MINOR.PATCH), источник правды
lisp/                 исходники AutoLISP (не правятся сборкой)
python/
  pyrx_onload.py
  igi_tools/          пакет команд
ui/igi_tools.cuix
bundle/               шаблон PackageContents + IGIToolsLoader.lsp
python-embed/         локальный runtime (gitignore, ~1 ГБ+)
scripts/
  Version.ps1         общая логика версий
  build-bundle.ps1
  deploy-dev.ps1
  build-installer.ps1
Makefile              обёртка над scripts/ + проброс ARGS
installer/IGITools-setup.iss
dist/                 результат сборки (gitignore)
```

Нужен [GNU Make](https://www.gnu.org/software/make/) в PATH (Git for Windows, scoop `make`, chocolatey `make`).

## Версионирование

Источник правды — файл [`VERSION`](VERSION) в корне (`MAJOR.MINOR.PATCH`). Сейчас база: **3.0.0**.

При каждой сборке bundle (и при deploy / installer, которые её вызывают) версия **увеличивается**, затем пишется в:

- `VERSION`
- `bundle/PackageContents.xml` → атрибут `AppVersion`
- `dist/IGITools.bundle/PackageContents.xml` (копия шаблона)
- установщик: `/DMyAppVersion=…` → `dist/IGITools-setup-<ver>.exe`

| `-Version` | Эффект (от текущего `VERSION`) |
|------------|--------------------------------|
| *(не указан)* или `patch` | +0.0.1 (например 3.0.0 → 3.0.1) |
| `minor` | +0.1.0, patch сбрасывается (3.0.5 → 3.1.0) |
| `major` | +1.0.0, minor/patch → 0 (3.2.4 → 4.0.0) |
| `X.Y.Z` | установить ровно эту версию (3.9.9 → 4.0.0 при `-Version 4.0.0`) |

`-NoBump` — не менять номер, только проставить текущий `VERSION` в `PackageContents.xml`.

Примеры:

```powershell
.\scripts\build-bundle.ps1 -SkipRuntime          # 3.0.0 → 3.0.1
.\scripts\build-bundle.ps1 -Version minor        # → 3.1.0
.\scripts\deploy-dev.ps1 -Version major          # → 4.0.0
.\scripts\build-installer.ps1 -Version 3.5.0     # зафиксировать 3.5.0
.\scripts\build-bundle.ps1 -NoBump               # остаться на текущей
```

Через Make:

```text
make bundle-fast
make bundle Version=minor
make deploy ARGS="-Version major"
make deploy-fast ARGS="-NoBump"
```

## Подготовка `python-embed`

Каталог **не** хранится в git. Нужен локально для сборки самодостаточного bundle.

1. Скачайте [Python 3.14 embeddable](https://www.python.org/downloads/windows/) (amd64) и распакуйте в `python-embed/`.
2. В `python314._pth` раскомментируйте `import site` (или добавьте строку).
3. Установите pip в embed (скачайте get-pip.py в `.\python-embed`):

```powershell
.\python-embed\python.exe .\get_pip.py
```

4. Установите пакеты:

```powershell
.\python-embed\python.exe -m pip install cad-pyrx
```

5. Проверьте наличие loaders:

```powershell
dir .\python-embed\Lib\site-packages\pyrx\RxLoader*.arx
```

## Dev-цикл (Make)

```text
make help
make version              # текущий VERSION
make deploy               # полный bundle + установка (admin; +patch)
make deploy-fast          # без копирования runtime
make deploy-junction      # junction → dist
make bundle / bundle-fast
make installer / installer-fast
make clean
```

Проброс **любых** аргументов целевого `.ps1`:

```text
make <target> ARGS="..."
make <target> Version=major|minor|patch|X.Y.Z
```

`Version=…` добавляет `-Version …`; `ARGS` дописывается как есть (можно комбинировать).

Типичный цикл:

1. Один раз `make deploy` (или `make deploy-junction` после `make bundle`).
2. Правки в `python/` или `lisp/`.
3. `make deploy-fast ARGS="-NoBump"` если номер версии менять не нужно, иначе просто `make deploy-fast` (+patch).
4. В CAD: `PYRELOAD` / `(adspyreload "...")` или перезапуск AutoCAD.

Перед `deploy*` закройте AutoCAD / Civil 3D — runtime DLL/PYD блокируются процессом.

Проверка: `PYRXVER`, `IGI_CIRCLES_ON_VERTICES`, `IGI_GZU_FROM_GEOJSON`, LISP-команды из `lisp/`.

## Скрипты и аргументы

Общий helper: [`scripts/Version.ps1`](scripts/Version.ps1) (подключается из build-скриптов, отдельно не вызывается).

### `scripts/build-bundle.ps1`

Собирает `dist\IGITools.bundle` (LISP → CP1251, Python, CUIX, опционально `python-embed`).

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `-RepoRoot` | string | родитель `scripts/` | Корень репозитория |
| `-SkipRuntime` | switch | off | Не копировать `python-embed` → `Contents/runtime` |
| `-Version` | string | *(пусто → patch)* | `patch` / `minor` / `major` / `X.Y.Z` — см. [Версионирование](#версионирование) |
| `-NoBump` | switch | off | Не увеличивать версию; взять текущий `VERSION` |

```powershell
.\scripts\build-bundle.ps1
.\scripts\build-bundle.ps1 -SkipRuntime -Version minor
.\scripts\build-bundle.ps1 -NoBump
```

### `scripts/deploy-dev.ps1`

Вызывает `build-bundle.ps1`, затем ставит bundle в ApplicationPlugins (нужны права admin для `Program Files`).

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `-RepoRoot` | string | родитель `scripts/` | Корень репозитория |
| `-TargetRoot` | string | `C:\Program Files\Autodesk\ApplicationPlugins` | Каталог ApplicationPlugins |
| `-SkipRuntime` | switch | off | Проброс в `build-bundle.ps1` |
| `-Junction` | switch | off | `mklink /J` на `dist\IGITools.bundle` вместо копирования |
| `-Version` | string | *(пусто → patch)* | Проброс в `build-bundle.ps1` |
| `-NoBump` | switch | off | Проброс в `build-bundle.ps1` |

```powershell
.\scripts\deploy-dev.ps1
.\scripts\deploy-dev.ps1 -SkipRuntime -NoBump
.\scripts\deploy-dev.ps1 -Junction -Version minor
.\scripts\deploy-dev.ps1 -TargetRoot "D:\Autodesk\ApplicationPlugins"
```

Если AutoCAD/Civil открыт и держит runtime — скрипт остановится с ошибкой до замены bundle.

### `scripts/build-installer.ps1`

По умолчанию собирает bundle, затем компилирует Inno Setup → `dist\IGITools-setup-<VERSION>.exe`.

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `-RepoRoot` | string | родитель `scripts/` | Корень репозитория |
| `-Version` | string | *(пусто → patch при сборке bundle)* | Проброс в `build-bundle.ps1`; при `-SkipBundle` — bump только `VERSION` для имени EXE (если задан) |
| `-IsccPath` | string | автопоиск | Явный путь к `ISCC.exe` |
| `-SkipRuntime` | switch | off | Проброс в `build-bundle.ps1` |
| `-SkipBundle` | switch | off | Не вызывать `build-bundle.ps1`; нужен готовый `dist\IGITools.bundle` |
| `-NoBump` | switch | off | Проброс в bundle / при `-SkipBundle` оставить `VERSION` |

Нужен [Inno Setup 6](https://jrsoftware.org/isinfo.php) (`ISCC.exe` в PATH или стандартной папке).

```powershell
.\scripts\build-installer.ps1
.\scripts\build-installer.ps1 -Version minor -SkipRuntime
.\scripts\build-installer.ps1 -SkipBundle -NoBump
.\scripts\build-installer.ps1 -IsccPath "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

Установщик (admin) пишет в:

`C:\Program Files\Autodesk\ApplicationPlugins\IGITools.bundle`

### Соответствие Make → скрипт

| Make | Скрипт | Зафиксированные флаги |
|------|--------|------------------------|
| `make bundle` | `build-bundle.ps1` | — |
| `make bundle-fast` | `build-bundle.ps1` | `-SkipRuntime` |
| `make deploy` | `deploy-dev.ps1` | — |
| `make deploy-fast` | `deploy-dev.ps1` | `-SkipRuntime` |
| `make deploy-junction` | `deploy-dev.ps1` | `-Junction` |
| `make installer` | `build-installer.ps1` | — |
| `make installer-fast` | `build-installer.ps1` | `-SkipRuntime` |
| `make version` | — | читает `VERSION` |
| `make clean` | — | удаляет `dist/` |

Дополнительно ко всем сборочным target: `Version=…` и/или `ARGS="…"`.

## Добавление LISP

1. Положите `.lsp` / `.vlx` в `lisp/` (исходники — **UTF-8**).
2. Пересоберите / задеплойте (`make deploy-fast`) — сборка конвертирует `.lsp` в **Windows-1251** для AutoCAD.
3. Команды вида `(defun c:NAME ...)` станут доступны после автозагрузки.

Кириллица в `(princ)` / `(alert)` корректна на русской Windows именно в ANSI (1251). UTF-8 с BOM AutoCAD часто читает как системную кодовую страницу → «РЅРµ РЅР°Р№РґРµРЅ…».

Загрузчик: [bundle/Contents/Lisp/IGIToolsLoader.lsp](bundle/Contents/Lisp/IGIToolsLoader.lsp).

## Добавление Python-команды

1. Создайте модуль в `python/igi_tools/commands/`, например `my_cmd.py`:

```python
from pyrx import command

@command(name="IGI_MY_CMD")
def my_cmd() -> None:
    print("hello from IGI")
```

2. Импортируйте модуль в `python/igi_tools/commands/__init__.py`.
3. Задеплойте и перезагрузите модуль в CAD.

UI с настройками: **wxPython** (входит в CADPyRx) — образцы в `PySamples/wxPython`. Простые команды — кнопки в **CUIX** (`ui/igi_tools.cuix`).

## CUIX

Файл: `ui/igi_tools.cuix`. Редактируйте в AutoCAD (`CUI`), сохраняйте partial customization, затем пересоберите bundle. В `PackageContents.xml` CUIX грузится с `LoadOnAutoCADStartup="True"`.

## Замечания

- Не используйте `%ProgramData%\Autodesk\ApplicationPlugins` как основной путь (ограничения AutoCAD 2026+).
- Не предлагайте `pyautocad` / `pythonnet` / .NET ObjectARX-обёртки — только CADPyRx.
- Консоль CAD: обычный `print()` из Python.
- Файл `VERSION` меняется сборкой — коммитьте его вместе с релизом, если нужна зафиксированная история номеров.
