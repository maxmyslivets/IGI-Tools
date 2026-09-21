<script setup>
import { ref, onMounted } from 'vue'

const RELEASES_URL = 'https://github.com/maxmyslivets/IGI-Tools/releases/latest'
const API_URL = 'https://api.github.com/repos/maxmyslivets/IGI-Tools/releases/latest'

const version = ref('')
const exeUrl = ref('')
const ready = ref(false)
const error = ref(false)

onMounted(async () => {
  try {
    const res = await fetch(API_URL, {
      headers: { Accept: 'application/vnd.github+json' }
    })
    if (!res.ok) throw new Error()
    const release = await res.json()
    version.value = (release.tag_name || '').replace(/^v/i, '')
    const asset = (release.assets || []).find(a => a.name.toLowerCase().endsWith('.exe'))
    exeUrl.value = asset ? asset.browser_download_url : RELEASES_URL
    ready.value = true
  } catch {
    error.value = true
    exeUrl.value = RELEASES_URL
    ready.value = true
  }
})
</script>

<template>
  <div class="download-banner">
    <div class="container">
      <div class="banner-card">
        <div class="banner-info">
          <svg class="banner-icon" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          <div class="banner-text">
            <span class="banner-title">Скачать IGI Tools</span>
            <span class="banner-sub">
              Последняя версия:
              <span v-if="ready && version" class="banner-ver">v{{ version }}</span>
              <span v-if="ready && !version" class="banner-ver">—</span>
              <span v-if="!ready" class="banner-ver banner-ver--loading">···</span>
            </span>
          </div>
        </div>
        <a
          class="banner-btn"
          :class="{ 'banner-btn--fallback': error }"
          :href="exeUrl || RELEASES_URL"
          target="_blank"
          rel="noopener noreferrer"
        >
          <span class="banner-btn-text">Скачать установщик</span>
          <svg class="banner-btn-arrow" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="5" y1="12" x2="19" y2="12" />
            <polyline points="12 5 19 12 12 19" />
          </svg>
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.download-banner {
  padding: 0 24px;
  margin-bottom: 16px;
}

@media (min-width: 640px) {
  .download-banner {
    padding: 0 48px;
  }
}

@media (min-width: 960px) {
  .download-banner {
    padding: 0 64px;
  }
}

.container {
  margin: 0 auto;
  max-width: 1152px;
}

.banner-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 20px 28px;
  border-radius: 12px;
  background: var(--vp-c-bg-soft, #f6f6f7);
  border: 1px solid var(--vp-c-divider, #e2e2e3);
}

.dark .banner-card {
  background: var(--vp-c-bg-soft, #252529);
}

.banner-info {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.banner-icon {
  flex-shrink: 0;
  color: var(--vp-c-brand-1, #42b883);
}

.banner-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.banner-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--vp-c-text-1);
  line-height: 1.3;
}

.banner-sub {
  font-size: 0.88rem;
  color: var(--vp-c-text-2);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.banner-ver {
  display: inline-block;
  padding: 1px 10px;
  border-radius: 5px;
  background: var(--vp-c-brand-1, #42b883);
  color: #fff;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  line-height: 1.5;
}

.banner-ver--loading {
  animation: pulse 1.2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.banner-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  padding: 11px 24px;
  border-radius: 10px;
  background: var(--vp-button-brand-bg, #42b883);
  color: var(--vp-button-brand-text, #fff) !important;
  font-size: 0.95rem;
  font-weight: 600;
  text-decoration: none;
  transition: transform 0.2s, box-shadow 0.2s, background 0.2s;
  white-space: nowrap;
}

.banner-btn:hover {
  transform: translateY(-1px);
  background: var(--vp-button-brand-hover-bg, #3ba676);
  color: var(--vp-button-brand-hover-text, #fff) !important;
  box-shadow: 0 4px 12px rgba(66, 184, 131, 0.35);
}

.banner-btn--fallback {
  background: var(--vp-c-gray-2, #888);
  box-shadow: none;
}

.banner-btn:active {
  transform: translateY(0);
}

.banner-btn-arrow {
  transition: transform 0.2s;
}

.banner-btn:hover .banner-btn-arrow {
  transform: translateX(3px);
}

@media (max-width: 639px) {
  .banner-card {
    flex-direction: column;
    align-items: flex-start;
    padding: 18px 20px;
  }

  .banner-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>