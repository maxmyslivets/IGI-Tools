---
# https://vitepress.dev/reference/default-theme-home-page
layout: home

hero:
  name: "IGI Tools"
  text: "Документация плагина"
  tagline: "Набор инструментов для эффективного создания инженерно-топографических планов в AutoCAD / Civil 3D"
#  image:
#    src: /icons/GEO_Tools.svg
#    alt: IGI Tools
  actions:
    - theme: brand
      text: Начало работы
      link: /guide/installation
    - theme: alt
      text: Все инструменты
      link: /guide/core-tools

features:
  - title: ⚡ Быстрая установка
    details: Установщик сам определяет версии AutoCAD / Civil 3D. После установки плагин подгружается при старте программы.
    link: /guide/installation
  - title: 🔧 Гибкие настройки
    details: Возможность изменения DWG-шаблона условных знаков СП 1.02.03-2025.
    link: /guide/settings
  - title: 🛠️ Инструменты вычерчивания
    details: Преобразование объектов в отметки, построение подпорных стен, выравнивание отметок вдоль линий, пересчет промеров колодцев в отметки.
    link: /guide/core-tools
  - title: 🧩 Специальные инструменты
    details: Импорт ГЗУ из GeoJSON, буферные зоны, расчет номенклатуры.
    link: /guide/gzu-import
  - title: ✨ Автоматизация
    details: Визуализация отметки из файла ЦМР во время перемещения курсора, мониторинг действий над объектами AutoCAD и автоматическое применение специализированных команд.
    link: /guide/dem-tracker
  - title: 🎨 Оформление чертежа
    details: Установка цветов слоёв и блоков, управление шаблоном условных знаков.
    link: /guide/colors-layers
---
