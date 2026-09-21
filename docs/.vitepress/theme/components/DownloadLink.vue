<script setup>
import { ref, onMounted } from 'vue'

const API_URL = 'https://api.github.com/repos/maxmyslivets/IGI-Tools/releases/latest'

const version = ref('')
const exeUrl = ref('')
const ready = ref(false)

onMounted(async () => {
  try {
    const res = await fetch(API_URL, {
      headers: { Accept: 'application/vnd.github+json' }
    })
    if (!res.ok) throw new Error()
    const release = await res.json()
    version.value = (release.tag_name || '').replace(/^v/i, '')
    const asset = (release.assets || []).find(a => a.name.toLowerCase().endsWith('.exe'))
    exeUrl.value = asset ? asset.browser_download_url : ''
    ready.value = true
  } catch {
    version.value = ''
    exeUrl.value = ''
    ready.value = true
  }
})
</script>

<template>
  <span v-if="ready && exeUrl" class="download-link">
    Скачайте установщик <a :href="exeUrl" target="_blank" rel="noopener noreferrer">IGI Tools v{{ version }}</a>
  </span>
  <span v-else-if="ready && !exeUrl">
    Скачайте установщик из <a href="https://github.com/maxmyslivets/IGI-Tools/releases/latest" target="_blank" rel="noopener noreferrer">последнего релиза</a>
  </span>
  <span v-else>Скачайте установщик из последнего релиза</span>
</template>