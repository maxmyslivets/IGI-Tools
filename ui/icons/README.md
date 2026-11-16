# IGI Tools — единый набор иконок

Все иконки для инструментов плагина [IGI-Tools](https://github.com/maxmyslivets/IGI-Tools)
из папок `lisp` и `python`, перерисованные в **одном стиле** по спецификации
`ui/icons/README.md` самого репозитория (Flat 2.0, палитра Civil 3D).

**45 иконок** · сетка 32×32 · прозрачный фон · чистый SVG без внешних зависимостей.

| Что покрыто | Количество |
|---|---|
| Команды LISP (`defun c:…`) | 23 |
| Команды Python (`@command(name=…)`) | 19 |
| Импорт точек из скомпилированного `Geo_Import_v2_10.VLX` | 1 |
| Служебные знаки интерфейса (вкладка ленты + «Справка») | 2 |
| **Всего** | **45** |

Покрытие команд — **100 %**: ни одна команда из `lisp/` и `python/` не осталась без иконки.
Ранее 19 команд использовали либо чужие стоковые иконки AutoCAD
(`RCDATA_16_*`, `POINT_CREATE_*`, `SURVEY_OBSERVATION_16`), либо не имели иконки вовсе.

---

## Как посмотреть

Откройте **`gallery.html`** — самодостаточная галерея (работает офлайн, без интернета):

* переключение **тёмной / светлой** темы CAD;
* просмотр в размерах **16 / 24 / 32 / 48 / 64 / 96 px** — сразу видно читаемость на ленте;
* поиск по команде, названию, описанию и файлу; фильтр LISP / Python / UI;
* клик по иконке → крупный вид на двух фонах, ряд размеров, исходный SVG,
  кнопки «Копировать SVG» и «Скачать SVG»;
* кнопка **«Скачать всё (ZIP)»** — весь набор одним архивом;
* таблица соответствия «команда → файл иконки».

Быстрый обзор без открытия галереи: `preview-dark.png`, `preview-light.png`,
`preview-ribbon-sizes.png` (проверка читаемости в 16 и 32 px).

---

## Дизайн-система

### Палитра (токены из спеки репозитория)

| Цвет | HEX | Роль в наборе |
|---|---|---|
| База | `#D9D9D9` | основной объект: геометрия, оси, листы, контуры |
| Акцент | `#89CBFA` | главное действие / результат команды |
| Нейтральный | `#808080` | источник данных, неактивное состояние |
| Контур | `#666666` | обводка базовых фигур, мелкие детали |
| Процесс | `#82D99F` | включение, автоматика, подтверждение |
| Модификатор | `#FFD580` | правка значения, редактирование |
| Статус | `#FF6666` | сброс, отключение, запрет |

### Геометрия

* **Сетка 32×32**, живая область `3…29` (отступ 3 px), фон прозрачный.
* **Толщины линий:** `2.0` основная · `1.5` второстепенная · `1.2` контур ·
  `2.4` глиф-модификатор. Все концы и соединения — круглые.
* **Скругления:** единый радиус `1.4` (мелкие элементы `0.8…1.2`).
* **Flat 2.0:** только сплошные цвета — без градиентов, теней, обводок-«свечений»
  и полупрозрачности.
* **Двухслойная композиция:** базовый объект снизу, глиф-модификатор в правом
  нижнем углу (центр `24,24`). Под модификатором база высечена по кругу `r = 7.6`
  через SVG-маску — слои никогда не «слипаются».

### Сквозные метафоры

Иконки строятся из повторяющихся примитивов, поэтому набор читается как семья:

* **Знак отметки** — полка + выноска + остриё в точке. Один и тот же глиф во всех
  командах про отметки; двойная полка = `H` и `Z` (СП_6.5.2), наклон вдоль линии =
  выравнивание подписей.
* **Кривые рельефа** — единая форма для всего семейства ЦМР.
* **Колодец** — кольцо с внутренним кольцом.
* **Лист с загнутым углом** — файл / шаблон DWG.
* **Пары «вкл/выкл»** отличаются только цветом и глифом модификатора:
  зелёный/акцент = включить, красный = сбросить (`SetLayerColors` ↔ `ResetLayerColors`,
  `WipeoutUncuff` ↔ `WipeoutCuff`, автоповорот вкл ↔ выкл, шаблон загрузить ↔ сбросить).
* **Направление преобразования** всегда «источник слева → результат справа»
  (`z2sp92` и `SP92ToPoints` — зеркальная пара).

---

## Состав набора

### Точки и отметки

| Команда | Назначение | Источник | Файл в репозитории | Иконка |
|---|---|---|---|---|
| `IGI_z2sp92` | Точки в отметки | LISP | `IGI_z2sp92.lsp` | `IGI_z2sp92.svg` |
| `IGI_z2sp652` | Точки в отметки бордюра | LISP | `IGI_z2sp652.lsp` | `IGI_z2sp652.svg` |
| `IGI_SP92ToPoints` | Отметки в точки | LISP | `IGI_SP92ToPoints.lsp` | `IGI_SP92ToPoints.svg` |
| `IGI_SelectSP92` | Выбрать отметки | LISP | `IGI_SelectSP92.lsp` | `IGI_SelectSP92.svg` |
| `IGI_BlockFan` | Создать веер деревьев | LISP | `IGI_BlockFan.lsp` | `IGI_BlockFan.svg` |
| `block2vertex` | Блок по вершинам | LISP | `BlockToVertex.lsp` | `IGI_BlockToVertex.svg` |
| `IGI_FIX_Z_SP92` | Внести поправки в отметки | LISP | `IGI_FIX_Z_SP92.lsp` | `IGI_FIX_Z_SP92.svg` |
| `IGI_FIX_Z_FROM_ATTR_SP92` | Перенести отметки на Z | LISP | `IGI_FIX_Z_FROM_ATTR_SP92.lsp` | `IGI_FIX_Z_FROM_ATTR_SP92.svg` |
| `IGI_Z0` | Обнуление чертежа | LISP | `IGI_Z0.lsp` | `igi_z0.svg` |
| `IGI_SEQNUM` | Нумерация текста | LISP | `IGI_Seqnum.lsp` | `IGI_SEQNUM.svg` |
| `IGI_SEQNUM_COPY` | Копия текста с +1 | LISP | `IGI_Seqnum_copy.lsp` | `IGI_SEQNUM_COPY.svg` |
| `CleanDynRotate` | Очистить динамический поворот | LISP | `CleanDynRotate.lsp` | `IGI_CleanDynRotate.svg` |
| `Geo_Import` | Импорт точек | LISP | `Geo_Import_v2_10.VLX` | `IGI_GeoImport.svg` |
### Рисование

| Команда | Назначение | Источник | Файл в репозитории | Иконка |
|---|---|---|---|---|
| `IGI_Podporka` | Подпорная стенка | LISP | `IGI_Podporka.lsp` | `IGI_Podporka.svg` |
| `IGI_FILL_AREA` | Заполнение объектами | Python | `commands/fill_area.py` | `IGI_FILL_AREA.svg` |
| `IGI_SLOPE_HATCH` | Штриховка откоса | Python | `commands/slope_hatch/` | `IGI_SLOPE_HATCH.svg` |
### ЦМР и рельеф

| Команда | Назначение | Источник | Файл в репозитории | Иконка |
|---|---|---|---|---|
| `IGI_DEM_MANAGER` | Менеджер ЦМР | Python | `commands/dem_manager.py` | `IGI_DEM_MANAGER.svg` |
| `IGI_DEM_TRACKER` | ЦМР-трекер | Python | `commands/dem_tracker.py` | `IGI_DEM_TRACKER.svg` |
| `IGI_DEM_TRACKER_STOP` | Остановить трекер | Python | `commands/dem_tracker.py` | `IGI_DEM_TRACKER_STOP.svg` |
| `IGI_ELEV_MARK` | Отметка в точке из ЦМР | Python | `commands/elev_mark/mark_point.py` | `IGI_ELEV_MARK.svg` |
| `IGI_ELEV_MARK_LINES` | Отметки по линии из ЦМР | Python | `commands/elev_mark/mark_lines.py` | `IGI_ELEV_MARK_LINES.svg` |
| `IGI_ELEV_MARK_GRID` | Отметки по сетке из ЦМР | Python | `commands/elev_mark/mark_grid.py` | `IGI_ELEV_MARK_GRID.svg` |
| `IGI_Interp` | Интерполяция горизонталей | LISP | `IGI_Interp.lsp` | `IGI_Interp.svg` |
### Коммуникации

| Команда | Назначение | Источник | Файл в репозитории | Иконка |
|---|---|---|---|---|
| `IGI_KolodecCalcZ` | Высчитать отметки труб | LISP | `IGI_KolodecCalcZ.lsp` | `IGI_KolodecCalcZ.svg` |
| `IGI_InsertKolodecAttrBlockText` | Вклинить отметку | LISP | `IGI_InsertKolodecAttrBlockText.lsp` | `IGI_InsertKolodecAttrBlockText.svg` |
| `IGI_BringKolodecBlocksToFront` | Люки на передний план | LISP | `IGI_BringKolodecBlocksToFront.lsp` | `IGI_BringKolodecBlocksToFront.svg` |
### Спец. инструменты

| Команда | Назначение | Источник | Файл в репозитории | Иконка |
|---|---|---|---|---|
| `IGI_GZU_FROM_GEOJSON` | Импорт GeoJSON | Python | `commands/gzu_from_geojson.py` | `IGI_GZU_FROM_GEOJSON.svg` |
| `IGI_DRAW_NOMENCLATURE` | Построение номенклатуры | Python | `commands/draw_nomenclature/` | `IGI_DRAW_NOMENCLATURE.svg` |
| `IGI_BUFFER_POLY` | Граница буфера | Python | `commands/buffer_poly.py` | `IGI_BUFFER_POLY.svg` |
| `IGI_GETTOTALAREAOFNESTEDPOLYGONS` | Площадь группы полигонов | Python | `commands/get_total_area_of_nested_polygons.py` | `IGI_GetTotalAreaOfNestedPolygons.svg` |
### Автоматизация

| Команда | Назначение | Источник | Файл в репозитории | Иконка |
|---|---|---|---|---|
| `IGI_ALIGN_SP92` | Отметки вдоль линии | Python | `commands/align_sp92.py` | `IGI_ALIGN_SP92.svg` |
| `IGI_register_reactor_auto_align_sp92` | Автоповорот отметок — вкл. | Python | `commands/auto_align_sp92.py` | `IGI_AUTO_ALIGN_ON.svg` |
| `IGI_unregister_reactor_auto_align_sp92` | Автоповорот отметок — выкл. | Python | `commands/auto_align_sp92.py` | `IGI_AUTO_ALIGN_OFF.svg` |
### Оформление чертежа

| Команда | Назначение | Источник | Файл в репозитории | Иконка |
|---|---|---|---|---|
| `IGI_SetLayerColors` | Раскрасить слои | LISP | `IGI_SetLayerColors.lsp` | `IGI_SetLayerColors.svg` |
| `IGI_ResetLayerColors` | Сбросить раскраску слоёв | LISP | `IGI_ResetLayerColors.lsp` | `IGI_ResetLayerColors.svg` |
| `IGI_SetManholeColors` | Раскрасить люки | LISP | `IGI_SetManholeColors.lsp` | `IGI_SetManholeColors.svg` |
| `IGI_ResetManholeColors` | Сбросить раскраску люков | LISP | `IGI_ResetManholeColors.lsp` | `IGI_ResetManholeColors.svg` |
| `IGI_WipeoutCuff` | Отключить маскировки | LISP | `IGI_WipeoutVisibility.lsp` | `IGI_DisableMasks.svg` |
| `IGI_WipeoutUncuff` | Восстановить маскировки | LISP | `IGI_WipeoutVisibility.lsp` | `IGI_RestoreMasks.svg` |
### Настройки и обслуживание

| Команда | Назначение | Источник | Файл в репозитории | Иконка |
|---|---|---|---|---|
| `IGI_LOAD_TEMPLATE` | Загрузить шаблон СП | Python | `commands/manage_template.py` | `IGI_LOAD_TEMPLATE.svg` |
| `IGI_RESET_TEMPLATE` | Сбросить шаблон СП | Python | `commands/manage_template.py` | `IGI_RESET_TEMPLATE.svg` |
| `IGI_CHECK_UPDATE` | Обновление | Python | `commands/check_update.py` | `IGI_CHECK_UPDATE.svg` |
| `IGI_RELOAD_ALL` | Перезагрузить модули | Python | `commands/reload_all.py` | `IGI_RELOAD_ALL.svg` |
| `IGI_TOOLS_BRAND` | Знак плагина | UI | `ui/igi_tools.cuix` | `IGI_Tools.svg` |
| `IGI_HELP` | Справка | UI | `ui/igi_tools.cuix` | `IGI_HELP.svg` |

---

## Имена файлов

Все **18 существующих имён** из `ui/icons/SVG/` сохранены без изменений — включая
`igi_z0.svg` (строчными), `IGI_GetTotalAreaOfNestedPolygons.svg`,
`IGI_DisableMasks.svg` / `IGI_RestoreMasks.svg`. Это значит, что ссылки в
`docs/guide/*.md` и в `igi_tools.cuix` продолжат работать после замены файлов.

Новые иконки названы по команде (`IGI_<COMMAND>.svg`), кроме случаев, где имя
команды слишком длинное или команда — переключатель:

| Команда | Файл |
|---|---|
| `block2vertex` | `IGI_BlockToVertex.svg` |
| `Geo_Import` | `IGI_GeoImport.svg` |
| `CleanDynRotate` | `IGI_CleanDynRotate.svg` |
| `IGI_register_reactor_auto_align_sp92` | `IGI_AUTO_ALIGN_ON.svg` |
| `IGI_unregister_reactor_auto_align_sp92` | `IGI_AUTO_ALIGN_OFF.svg` |
| знак плагина | `IGI_Tools.svg` |
| кнопка «Справка» | `IGI_HELP.svg` |

---

## Как подключить

**Документация (VitePress).** SVG используется напрямую — просто замените файлы
в `docs/public/icons/` (и `ui/icons/SVG/`):

```
cp svg/*.svg  <репозиторий>/ui/icons/SVG/
cp svg/*.svg  <репозиторий>/docs/public/icons/
```

**Лента AutoCAD / Civil 3D.** CUIX ссылается на **растровые** BMP 16×16 и 32×32
(`<SmallImage Name="…bmp"/>`, `<LargeImage Name="…_32.bmp"/>`), поэтому для ленты
SVG нужно растеризовать в BMP и положить в `ui/icons/BMP/`, а затем обновить
`SmallImage` / `LargeImage` в `igi_tools.cuix`. Сейчас в ленте 21 команда сидит на
стоковых иконках AutoCAD — их достаточно переназначить на новые файлы.
Этот шаг (BMP + патч CUIX) в поставку не входит — набор отдан в векторе.

---

## Пересборка

Иконки не рисовались вручную по одной — они генерируются из общих примитивов,
поэтому толщины, радиусы и метафоры гарантированно одинаковы во всём наборе.

```bash
python3 tools/build_icons.py     # → svg/*.svg + icons.json
python3 tools/build_gallery.py   # → gallery.html
python3 tools/build_readme.py    # → README.md
```

Точка настройки стиля — блок токенов в начале `tools/build_icons.py`
(`BASE`, `ACC`, `NEU`, `OUT`, `PRC`, `MOD`, `STA`, `W_*`, `RX`, `BADGE_*`).
Правка одного токена перекрашивает весь набор целиком.

---

## Примечания

* **Светлая тема.** Палитра спеки рассчитана на тёмный интерфейс Civil 3D, поэтому
  базовый `#D9D9D9` на белом фоне выглядит бледно — ровно как и прежние иконки
  репозитория. Набор оставлен строго в спеке; при необходимости светлый вариант
  делается сменой токенов (`BASE` → тёмно-серый, `OUT` → темнее) и пересборкой.
* **`Geo_Import`** — скомпилированный `Geo_Import_v2_10.VLX`, исходников в папке нет;
  иконка сделана по назначению команды из ленты («Импорт точек»).
* **`lisp/IGI_ElevMark_insert.lsp`** — служебная библиотека без команды `c:…`,
  иконка не нужна.
* **`IGI_DEM_MANAGER`** зарегистрирован в двух модулях (`dem_manager.py` и
  `dem_tracker.py`) — иконка одна.
* `IGI_SLOPE_HATCH`, `IGI_SEQNUM`, `IGI_SEQNUM_COPY`, `CleanDynRotate`,
  `IGI_RELOAD_ALL`, `IGI_DEM_TRACKER_STOP` и переключатели автоповорота на ленту
  не вынесены, но иконки для них есть — набор покрывает все команды, а не только
  текущую раскладку ленты.
