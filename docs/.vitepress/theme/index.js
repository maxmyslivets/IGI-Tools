import { h } from 'vue'
import DefaultTheme from 'vitepress/theme'
import DownloadBanner from './components/DownloadBanner.vue'
import DownloadLink from './components/DownloadLink.vue'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('DownloadLink', DownloadLink)
  },
  Layout() {
    return h(DefaultTheme.Layout, null, {
      'home-features-before': () => h(DownloadBanner)
    })
  }
}