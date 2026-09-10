# Инструменты IGI Tools

Справочник по всем командам плагина. Выберите раздел:

---

<div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; margin:24px 0;">

<a href="/guide/align-labels" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Выравнивание подписей</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">IGI_ALIGN_SP92, автовыравнивание вдоль дорожной сети</div>
</a>

<a href="/guide/blocks-points" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Блоки и точки</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">z2sp92, z2sp652, SP92ToPoints, SelectSP92, BlockToVertex, BlockFan</div>
</a>

<a href="/guide/manholes" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Работа с колодцами</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">InsertKolodecAttrBlockText, KolodecCalcZ</div>
</a>

<a href="/guide/elevation" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Высоты и Z-координаты</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">IGI_Z0, FIX_Z_SP92, FIX_Z_FROM_ATTR_SP92</div>
</a>

<a href="/guide/dem-tracker" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">DEM-трекер</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">IGI_DEM_TRACKER, высота поверхности под курсором</div>
</a>

<a href="/guide/buffer-poly" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Построение буферных зон</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">IGI_BUFFER_POLY</div>
</a>

<a href="/guide/nomenclature" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Сетка номенклатуры</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">IGI_DRAW_NOMENCLATURE, сетка 250×250 м</div>
</a>

<a href="/guide/gzu-import" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Импорт ГЗУ</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">IGI_GZU_FROM_GEOJSON</div>
</a>

<a href="/guide/fill-area" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Заливка области</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">IGI_FILL_AREA, расстановка блоков и текста</div>
</a>

<a href="/guide/interpolation" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Интерполяция горизонталей</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">IGI_Interp</div>
</a>

<a href="/guide/podporka" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Подпорки (сечения)</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">IGI_Podporka</div>
</a>

<a href="/guide/colors-layers" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Цвета слоёв и блоков</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">Set/ResetLayerColors, Set/ResetManholeColors</div>
</a>

<a href="/guide/maintenance" style="display:block; padding:16px; border:1px solid var(--vp-c-divider); border-radius:8px; text-decoration:none; color:inherit; transition:border-color .2s;">
  <div style="font-weight:600; font-size:1.05em;">Очистка и обслуживание</div>
  <div style="font-size:.87em; opacity:.7; margin-top:4px;">CleanDynRotate, IGI_RELOAD_ALL</div>
</a>

</div>

---

## Быстрый доступ

- [Установка и удаление](/guide/installation)
- [Настройки](/guide/settings) — проверка обновлений, управление шаблоном