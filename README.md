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

При наличии новой версии на [Releases](https://github.com/maxmyslivets/IGI-Tools/releases) плагин предложит обновление и откроет скачивание установщика в браузере. Перед установкой закройте AutoCAD / Civil 3D.

## Настройка шаблона

Некоторые команды берут блоки, типы линий, слои и прочее из файла шаблона
`Contents\Resources\template.dwg`. Рядом лежит заводской эталон `template.default.dwg`
(актуальная копия из дистрибутива; обновляется при каждой установке).

В поставке лежит стандартный шаблон (ВОИИ Государственное предприятие "Геосервис").
Если в организации свои блоки/оформление — **замените шаблон один раз** после установки:

| Команда | Назначение |
|---------|------------|
| `IGI_LOAD_TEMPLATE` | Выбрать свой DWG; он копируется как `template.dwg`. Текущий файл сохраняется как `template.dwg.bak` |
| `IGI_RESET_TEMPLATE` | Вернуть в `template.dwg` заводской шаблон из `template.default.dwg` (версия из последнего установщика) |

**При обновлении / переустановке**, если `template.dwg` уже есть, установщик показывает опцию «Обновить активный шаблон DWG» (**по умолчанию включена**):

- **галочка включена** — `template.dwg` заменяется файлом из дистрибутива;
- **галочка снята** — ваш `template.dwg` (и `.bak`) не трогаются.

`template.default.dwg` обновляется всегда, поэтому `IGI_RESET_TEMPLATE` возвращает актуальный шаблон из установщика, а не содержимое `.bak`.

## Проверка

| Что проверить | Команда / действие |
|---------------|-------------------|
| CADPyRx загружен | `PYRXVER` или `PYRXLOADLOG` |
| Python-утилита | например `IGI_DRAW_NOMENCLATURE`, `IGI_GZU_FROM_GEOJSON`, `IGI_CHECK_UPDATE` |
| Шаблон DWG | `IGI_LOAD_TEMPLATE` / `IGI_RESET_TEMPLATE` |
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
- **Нет блока при импорте ГЗУ** — проверьте `Contents\Resources\template.dwg` и при необходимости загрузите свой файл командой `IGI_LOAD_TEMPLATE`.
