import { h } from 'vue'
import DefaultTheme from 'vitepress/theme'
import DownloadBanner from './components/DownloadBanner.vue'
import DownloadLink from './components/DownloadLink.vue'
import RoadmapCarousel from './components/RoadmapCarousel.vue'
import LatestReleases from './components/LatestReleases.vue'
import ReleaseHistory from './components/ReleaseHistory.vue'
import TelegramContact from './components/TelegramContact.vue'

const components = [DownloadBanner, DownloadLink, RoadmapCarousel, LatestReleases, ReleaseHistory]

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    components.forEach(c => app.component(c.name || c.__name, c))
  },
  Layout() {
    return h(DefaultTheme.Layout, null, {
      'home-features-before': () => h(DownloadBanner),
      'home-hero-actions-after': () => h(RoadmapCarousel),
      'nav-bar-content-after': () => h(TelegramContact)
    })
  }
}