import { defineConfig } from 'vitepress'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "IGI Tools",
  description: "Документация плагина для AutoCAD / Civil 3D",
  base: '/IGI-Tools/',
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    nav: [
      { text: 'Главная', link: '/' },
      { text: 'Инструменты', link: '/guide/core-tools' },
    ],

    sidebar: [
      {
        text: 'Начало работы',
        items: [
          { text: 'Установка', link: '/guide/installation' },
          { text: 'Настройки', link: '/guide/settings' }
        ]
      },
      {
        text: 'Инструменты',
        items: [
          { text: 'Все инструменты', link: '/guide/core-tools' },
          {
            text: 'Точки и отметки',
            collapsed: true,
            items: [
              { text: 'Создание отметок', link: '/guide/blocks-points' },
              { text: 'Корректировка высот', link: '/guide/elevation' },
              { text: 'Выравнивание подписей', link: '/guide/align-labels' },
            ]
          },
          {
            text: 'Рисование',
            collapsed: true,
            items: [
              { text: 'Подпорные стенки', link: '/guide/podporka' },
              { text: 'Заливка области', link: '/guide/fill-area' },
            ]
          },
          {
            text: 'ЦМР и рельеф',
            collapsed: true,
            items: [
              { text: 'Подключить ЦМР', link: '/guide/open-dem' },
              { text: 'Интерполяция горизонталей', link: '/guide/interpolation' },
            ]
          },
          {
            text: 'Автоматизация',
            collapsed: true,
            items: [
              { text: 'DEM-трекер', link: '/guide/dem-tracker' },
              { text: 'Автоповорот отметок', link: '/guide/auto-align-labels' },
            ]
          },
          {
            text: 'Коммуникации',
            collapsed: true,
            items: [
              { text: 'Работа с колодцами', link: '/guide/manholes' },
            ]
          },
          {
            text: 'Специальные инструменты',
            collapsed: true,
            items: [
              { text: 'Импорт ГЗУ', link: '/guide/gzu-import' },
              { text: 'Буферные зоны', link: '/guide/buffer-poly' },
              { text: 'Сетка номенклатуры', link: '/guide/nomenclature' },
              { text: 'Исправление чертежа', link: '/guide/fix-draw' },
            ]
          },
          {
            text: 'Оформление чертежа',
            collapsed: true,
            items: [
              { text: 'Цвета слоёв и блоков', link: '/guide/colors-layers' },
            ]
          },
        ]
      },
      {
        text: 'История изменений',
        items: [
          { text: 'Все релизы', link: '/guide/changelog' }
        ]
      }
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/maxmyslivets/IGI-Tools' }
    ]
  }
})