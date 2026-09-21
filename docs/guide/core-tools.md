# Инструменты IGI Tools

Справочник по всем командам плагина, сгруппированный по функциональным разделам.

---

## 📍 Точки и отметки

Преобразование объектов в высотные отметки, корректировка и выравнивание подписей.

<div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; margin:24px 0;">

  <a href="./blocks-points" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Создание отметок</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">z2sp92, z2sp652, SP92ToPoints, SelectSP92, BlockFan, BlockToVertex</div>
</a>

  <a href="./elevation" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Корректировка высот</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">FIX_Z_SP92, FIX_Z_FROM_ATTR_SP92, Z0 — обнуление чертежа</div>
</a>

  <a href="./align-labels" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Выравнивание подписей</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">AlignSP92 — разворот подписей вдоль линии</div>
</a>

</div>

---

## ✏️ Рисование

Автоматическая расстановка объектов и элементов оформления.

<div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; margin:24px 0;">

  <a href="./podporka" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Подпорные стенки</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">IGI_Podporka — расстановка блоков СП_3.59.2 вдоль оси</div>
</a>

  <a href="./fill-area" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Заливка области</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">IGI_FILL_AREA — расстановка блоков и текста внутри контура</div>
</a>

</div>

---

## ⛰️ ЦМР и рельеф

Построение горизонталей по высотным отметкам.

<div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; margin:24px 0;">

  <a href="./interpolation" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Интерполяция горизонталей</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">IGI_Interp — построение полуметровых горизонталей между отметками</div>
</a>

</div>

---

## 🤖 Автоматизация

Фоновые процессы: отслеживание высоты ЦМР под курсором и автоматический поворот отметок.

<div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; margin:24px 0;">

  <a href="./dem-tracker" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">DEM-трекер</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">Высота поверхности под курсором в реальном времени</div>
</a>

  <a href="./align-labels" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Автоповорот отметок дорог</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">IGI_register_reactor_auto_align_sp92 — автоматический разворот блоков на слое дорожной сети</div>
</a>

</div>

---

## 🔌 Коммуникации

Инструменты для работы с блоками канализационных колодцев.

<div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; margin:24px 0;">

  <a href="./manholes" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Работа с колодцами</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">KolodecCalcZ, InsertKolodecAttrBlockText — расчёт и вставка отметок труб</div>
</a>

</div>

---

## 🧩 Специальные инструменты

Импорт данных, построение буферов и сетки номенклатуры.

<div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; margin:24px 0;">

  <a href="./gzu-import" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Импорт ГЗУ</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">IGI_GZU_FROM_GEOJSON — границы землепользования из GeoJSON</div>
</a>

  <a href="./buffer-poly" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Буферные зоны</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">IGI_BUFFER_POLY — объединённые полигоны вокруг линий</div>
</a>

  <a href="./nomenclature" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Сетка номенклатуры</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">IGI_DRAW_NOMENCLATURE — разграфка 250×250 м</div>
</a>

</div>

---

## 🎨 Оформление чертежа

Настройка цветов слоёв, блоков и управление шаблоном.

<div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; margin:24px 0;">

  <a href="./colors-layers" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Цвета слоёв и блоков</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">Set/ResetLayerColors, Set/ResetManholeColors</div>
</a>

</div>

---

## Быстрый доступ

- [Установка и удаление](/guide/installation)
- [Настройки](/guide/settings) — проверка обновлений, управление шаблоном