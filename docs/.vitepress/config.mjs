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
          { text: 'Выравнивание подписей', link: '/guide/align-labels' },
          { text: 'Блоки и точки', link: '/guide/blocks-points' },
          { text: 'Работа с колодцами', link: '/guide/manholes' },
          { text: 'Высоты и Z-координаты', link: '/guide/elevation' },
          { text: 'DEM-трекер', link: '/guide/dem-tracker' },
          { text: 'Буферные зоны', link: '/guide/buffer-poly' },
          { text: 'Сетка номенклатуры', link: '/guide/nomenclature' },
          { text: 'Импорт ГЗУ', link: '/guide/gzu-import' },
          { text: 'Заливка области', link: '/guide/fill-area' },
          { text: 'Интерполяция', link: '/guide/interpolation' },
          { text: 'Подпорки', link: '/guide/podporka' },
          { text: 'Цвета слоёв и блоков', link: '/guide/colors-layers' },
          { text: 'Очистка и обслуживание', link: '/guide/maintenance' },
        ]
      }
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/maxmyslivets/IGI-Tools' }
    ]
  }
})