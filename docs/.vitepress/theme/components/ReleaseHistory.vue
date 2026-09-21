<template>
  <div class="release-history">
    <div v-if="loading" class="rh-status">Загрузка истории изменений…</div>
    <div v-else-if="error" class="rh-status rh-error">{{ error }}</div>

    <div v-for="release in releases" :key="release.tag_name" class="rh-release">
      <h2 :id="release.tag_name">
        <a :href="release.html_url" class="rh-version" target="_blank">{{ release.tag_name }}</a>
        <span class="rh-date">{{ formatDate(release.published_at) }}</span>
      </h2>
      <div v-if="release.body" class="rh-body" v-html="renderBody(release.body)"></div>
      <p v-else class="rh-empty">Нет описания.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import MarkdownIt from 'markdown-it'

const loading = ref(true)
const error = ref(null)
const releases = ref([])

const GITHUB_API = 'https://api.github.com/repos/maxmyslivets/IGI-Tools/releases?per_page=50'

const md = new MarkdownIt({
  html: true,
  linkify: true,
  breaks: true,
})

function proxyGithubImages(s) {
  return s.replace(
    /\bhttps:\/\/github\.com\/user-attachments\/[^\s"'<)]+/g,
    u => 'https://wsrv.nl/?url=' + encodeURIComponent(u)
  )
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('ru-RU', { year: 'numeric', month: 'long', day: 'numeric' })
}

function renderBody(body) {
  if (!body) return ''
  return md.render(proxyGithubImages(body))
}

onMounted(async () => {
  try {
    const res = await fetch(GITHUB_API)
    if (!res.ok) throw new Error(`GitHub API: ${res.status} ${res.statusText}`)
    const data = await res.json()
    releases.value = data
  } catch (e) {
    error.value = `Не удалось загрузить историю: ${e.message}`
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.release-history {
  max-width: 800px;
  margin: 0 auto;
  padding: 0 24px 48px;
}
.rh-status {
  text-align: center;
  padding: 48px 0;
  font-size: 1rem;
  color: var(--vp-c-text-2);
}
.rh-error {
  color: var(--vp-c-danger-1);
}
.rh-release {
  margin-bottom: 36px;
}
.rh-release h2 {
  display: flex;
  align-items: baseline;
  gap: 12px;
  border: none;
  padding: 0;
  margin: 0 0 12px;
}
.rh-version {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--vp-c-brand-1) !important;
  text-decoration: none;
}
.rh-version:hover {
  text-decoration: underline;
}
.rh-date {
  font-size: 0.85rem;
  color: var(--vp-c-text-3);
}
.rh-body {
  font-size: 0.95rem;
  line-height: 1.65;
  color: var(--vp-c-text-1);
}
.rh-body p {
  margin: 0 0 8px;
}
.rh-body ul {
  padding-left: 20px;
  margin: 0 0 8px;
}
.rh-body li {
  line-height: 1.5;
}
.rh-body code {
  font-family: var(--vp-font-family-mono);
  font-size: 0.85em;
  background: var(--vp-c-bg-mute);
  border-radius: 4px;
  padding: 0 4px;
}
.rh-body pre {
  background: var(--vp-c-bg-mute);
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
}
.rh-body img {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
}
.rh-body img {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
}
.rh-empty {
  font-size: 0.9rem;
  color: var(--vp-c-text-3);
  font-style: italic;
}
</style>