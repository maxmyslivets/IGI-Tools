<template>
  <h2 class="lc-heading">Последние изменения</h2>

  <div class="lc-card">
    <div v-if="loading" class="lc-status">Загрузка изменений…</div>
    <div v-else-if="error" class="lc-status lc-error">{{ error }}</div>

    <div v-for="release in releases" :key="release.tag_name" class="lc-release">
      <div class="lc-version">
        <a :href="release.html_url" class="lc-version-link" target="_blank">
          {{ release.tag_name }}
        </a>
        <span v-if="release.published_at" class="lc-date">{{ formatDate(release.published_at) }}</span>
      </div>
      <div v-if="release.body" class="lc-body" v-html="renderBody(release.body)"></div>
      <div v-else class="lc-empty">Нет описания.</div>
    </div>

    <a href="./guide/changelog" class="lc-button">Все изменения →</a>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import MarkdownIt from 'markdown-it'

const loading = ref(true)
const error = ref(null)
const releases = ref([])

const GITHUB_API = 'https://api.github.com/repos/maxmyslivets/IGI-Tools/releases?per_page=2'

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
    if (!res.ok) throw new Error(`GitHub API: ${res.status}`)
    const data = await res.json()
    releases.value = Array.isArray(data) ? data : []
  } catch (e) {
    error.value = `Не удалось загрузить изменения: ${e.message}`
  } finally {
    loading.value = false
  }
})
</script>

<style>
.lc-heading {
  font-size: 1.8rem;
  font-weight: 600;
  margin: 48px 0 24px;
  border-bottom: 1px solid var(--vp-c-divider);
  padding-bottom: 12px;
}
.lc-card {
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  padding: 24px;
}
.lc-status {
  font-size: 0.95rem;
  color: var(--vp-c-text-2);
}
.lc-error {
  color: var(--vp-c-danger-1);
}
.lc-release {
  margin-bottom: 20px;
  background: transparent;
  border: none;
}
.lc-version {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--vp-c-brand-1);
  margin-bottom: 8px;
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.lc-version-link {
  color: var(--vp-c-brand-1) !important;
  text-decoration: none;
}
.lc-version-link:hover {
  text-decoration: underline;
}
.lc-date {
  font-size: 0.82rem;
  color: var(--vp-c-text-3);
}
.lc-body {
  font-size: 0.92rem;
  line-height: 1.6;
  color: var(--vp-c-text-2);
}
.lc-body p {
  margin: 0 0 8px;
}
.lc-body ul {
  margin: 0 0 8px;
  padding-left: 20px;
}
.lc-body li {
  line-height: 1.5;
}
.lc-body code {
  font-family: var(--vp-font-family-mono);
  font-size: 0.85em;
  background: var(--vp-c-bg-mute);
  border-radius: 4px;
  padding: 0 4px;
}
.lc-body img {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
}
.lc-empty {
  font-size: 0.85rem;
  font-style: italic;
  color: var(--vp-c-text-3);
}
.lc-button {
  display: inline-block;
  margin-top: 16px;
  padding: 8px 20px;
  background: var(--vp-button-brand-bg);
  color: #fff !important;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.9rem;
  text-decoration: none;
  transition: background 0.2s;
  border: none;
  cursor: pointer;
}
.lc-button:hover {
  background: var(--vp-c-brand-2);
}
</style>