<template>
  <div class="roadmap-carousel">
    <div class="carousel-panel">
      <div class="carousel-header">В следующих релизах</div>
      <div class="carousel-viewport" ref="viewportRef">
        <div class="carousel-track" ref="trackRef">
          <div
            v-for="(item, i) in duplicatedItems"
            :key="i"
            class="carousel-item"
            :style="transforms[i]"
          >
            <span class="item-title">{{ item.title }}</span>
            <span class="item-desc">{{ item.desc }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import items from '../data/roadmap.json'

const duplicatedItems = [...items, ...items, ...items]
const NUM_COPIES = 3

const viewportRef = ref(null)
const trackRef = ref(null)
const transforms = ref([])

let animId = null
let scrollY = 0

onMounted(() => {
  nextTick(() => {
    const vp = viewportRef.value
    const track = trackRef.value
    if (!vp || !track) return

    transforms.value = duplicatedItems.map(() => ({}))

    const animate = () => {
      const vpHeight = vp.clientHeight
      const vpCenter = vpHeight / 2
      const children = Array.from(track.children)
      if (!children.length) {
        animId = requestAnimationFrame(animate)
        return
      }

      const heights = children.map(el => el.scrollHeight)
      const totalH = heights.reduce((s, h) => s + h, 0)
      const period = totalH / NUM_COPIES
      if (totalH === 0 || !Number.isFinite(period) || period <= 0) {
        animId = requestAnimationFrame(animate)
        return
      }

      scrollY = (scrollY + 0.2) % period
      track.style.transform = `translateY(${-scrollY}px)`

      const next = []
      let y = 0
      for (let i = 0; i < children.length; i++) {
        const h = heights[i]
        const center = y - scrollY + h / 2
        let dist = Math.abs(center - vpCenter) / (vpHeight * 0.55)
        dist = Math.min(dist, 1)

        const scale = 1 - dist * 0.25
        next.push({
          transform: `scale(${scale})`,
          opacity: 1 - dist * 0.950,
        })
        y += h
      }

      transforms.value = next
      animId = requestAnimationFrame(animate)
    }

    animId = requestAnimationFrame(animate)
  })
})

onUnmounted(() => {
  if (animId) cancelAnimationFrame(animId)
})
</script>

<style scoped>
.roadmap-carousel {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  pointer-events: none;
  z-index: 5;
}

.carousel-panel {
  width: 400px;
  max-height: 400px;
  padding: 20px 18px;
  pointer-events: auto;
  margin-right: 48px;
}

.carousel-header {
  font-size: 0.82rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--vp-c-text-2);
  margin-bottom: 14px;
  text-align: center;
  opacity: 0.9;
}

.carousel-viewport {
  height: 300px;
  overflow: hidden;
  mask-image: linear-gradient(to bottom, transparent 0%, black 8%, black 92%, transparent 100%);
  -webkit-mask-image: linear-gradient(to bottom, transparent 0%, black 8%, black 92%, transparent 100%);
}

.carousel-track {
  display: flex;
  flex-direction: column;
  will-change: transform;
}

.carousel-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  transform-origin: center center;
  will-change: transform, opacity;
  padding: 12px 0;
}

.item-title {
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--vp-c-brand-1);
  line-height: 1.35;
  margin-bottom: 3px;
}

.item-desc {
  font-size: 0.8rem;
  color: var(--vp-c-text-2);
  line-height: 1.45;
}
</style>

<style>
.VPHomeHero {
  position: relative !important;
}
@media (max-width: 960px) {
  .roadmap-carousel {
    display: none !important;
  }
}
</style>