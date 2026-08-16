# IGI Tools

Плагин для **AutoCAD / Civil 3D** (2022–2027): AutoLISP-утилиты и Python-команды на [CADPyRx](https://github.com/CEXT-Dan/PyRx).

Установщик кладёт самодостаточный bundle (встроенный Python + CADPyRx) в:

`C:\Program Files\Autodesk\ApplicationPlugins\IGITools.bundle`

Плагин подхватывается автозагрузчиком Autodesk при старте CAD.

## Требования

- Windows 10/11 x64
- AutoCAD или Civil 3D **2022–2027** (полная версия с поддержкой ARX; **не** LT)
- Права администратора для установки

## Установка

1. Закройте AutoCAD / Civil 3D.
2. Запустите `IGITools-setup-1.0.0.exe` от имени администратора.
3. Дождитесь копирования в `ApplicationPlugins\IGITools.bundle`.
4. Запустите CAD заново.

После старта в командной строке должны появиться сообщения `[IGI Tools]`.

## Проверка

| Что проверить | Команда / действие |
|---------------|-------------------|
| CADPyRx загружен | `PYRXVER` или `PYRXLOADLOG` |
| Python-утилита | `IGI_DRAW_NOMENCLATURE`, `IGI_GZU_FROM_GEOJSON` |
| LISP | например `BlockFan`, `INTERP`, `FILLBLOCK`, `PODPORKA` |
| Интерфейс | вкладка/панель из `igi_tools.cuix` (если настроена в CUIX) |

### `IGI_GZU_FROM_GEOJSON`

1. Введите `IGI_GZU_FROM_GEOJSON`.
2. Выберите файл GeoJSON (стандартный или формат gismap.by).
3. В модель добавляются замкнутые полилинии границ (слой `0`) и блоки «СП_1.5» в вершинах.

## Удаление

Через «Программы и компоненты» / Uninstall из меню Пуск, либо удалите папку:

`C:\Program Files\Autodesk\ApplicationPlugins\IGITools.bundle`

## Устранение проблем

- **Плагин не грузится** — убедитесь, что bundle лежит в `Program Files\...\ApplicationPlugins` (не в `ProgramData`; с AutoCAD 2026 путь ProgramData ограничен).
- **Предупреждения о доверенных путях** — добавьте каталог bundle в `TRUSTEDPATHS` или разрешите загрузку при запросе.
- **Нет Python-команд** — выполните `PYRXLOADLOG`; проверьте наличие `Contents\Python\pyrx_onload.py` и `Contents\runtime\Lib\site-packages\pyrx\RxLoader*.arx`.
- **LISP не видны** — проверьте `Contents\Lisp\` и сообщение загрузчика в командной строке.

