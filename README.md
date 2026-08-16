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
2. Запустите `IGITools-setup-{VERSION}.exe` от имени администратора.
3. Дождитесь копирования в `ApplicationPlugins\IGITools.bundle`.
4. Запустите CAD заново.

После старта в командной строке должны появиться сообщения `[IGI Tools]`.

При наличии новой версии на [Releases](https://github.com/maxmyslivets/IGI-Tools/releases) плагин предложит обновление: скачает установщик и попросит закрыть AutoCAD / Civil 3D перед запуском.

## Проверка

| Что проверить | Команда / действие |
|---------------|-------------------|
| CADPyRx загружен | `PYRXVER` или `PYRXLOADLOG` |
| Python-утилита | например `IGI_DRAW_NOMENCLATURE`, `IGI_GZU_FROM_GEOJSON`, `IGI_CHECK_UPDATE` |
| LISP | например `BlockFan`, `INTERP`, `FILLBLOCK`, `PODPORKA` |
| Интерфейс | вкладка/панель из `igi_tools.cuix` |

## Удаление

Через «Программы и компоненты» / Uninstall из меню Пуск, либо удалите папку:

`C:\Program Files\Autodesk\ApplicationPlugins\IGITools.bundle`

## Устранение проблем

- **Плагин не грузится** — убедитесь, что bundle лежит в `Program Files\...\ApplicationPlugins` (не в `ProgramData`; с AutoCAD 2026 путь ProgramData ограничен).
- **Предупреждения о доверенных путях** — добавьте каталог bundle в `TRUSTEDPATHS` или разрешите загрузку при запросе.
- **Нет Python-команд** — выполните `PYRXLOADLOG`; проверьте наличие `Contents\Python\pyrx_onload.py` и `Contents\runtime\Lib\site-packages\pyrx\RxLoader*.arx`.
- **LISP не видны** — проверьте `Contents\Lisp\` и сообщение загрузчика в командной строке.

