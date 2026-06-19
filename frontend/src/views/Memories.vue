<template>
  <div class="mem">
    <header class="mem-header">
      <h1>回忆</h1>
      <p class="mem-sub">那年今日 · {{ prettyDate }}</p>
    </header>

    <div v-if="loading" class="mem-loading">
      <el-icon class="is-loading" size="22"><Loading /></el-icon>
    </div>

    <div v-else-if="groups.length === 0" class="mem-empty">
      <el-icon size="40"><Sunrise /></el-icon>
      <p>今天还没有往年的回忆</p>
      <span>等照片库积累更久，或换一天再来看看</span>
    </div>

    <div v-else class="mem-groups">
      <section v-for="g in groups" :key="g.year" class="mem-group">
        <div class="mem-group-head">
          <span class="mem-years-ago">{{ g.years_ago }} 年前</span>
          <span class="mem-year">{{ g.year }} 年 · {{ g.count }} 张</span>
        </div>
        <div class="mem-grid" :style="{ gridTemplateColumns: `repeat(${columns}, 1fr)` }">
          <div
            v-for="photo in g.photos"
            :key="photo.id"
            class="mem-cell"
            @click="openViewer(g.photos, photo)"
          >
            <img :src="`/api/v1/thumbnails/${photo.id}?size=256`" loading="lazy" />
            <div v-if="photo.media_type === 'video'" class="mem-video-badge">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
            </div>
          </div>
        </div>
      </section>
    </div>

    <ImageViewer
      :visible="!!viewerPhoto"
      :photo="viewerPhoto"
      :has-prev="viewerIndex > 0"
      :has-next="viewerIndex < viewerList.length - 1"
      @close="viewerPhoto = null"
      @navigate="navigateViewer"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading, Sunrise } from '@element-plus/icons-vue'
import ImageViewer from '@/components/gallery/ImageViewer.vue'
import { memoriesApi, type MemoryGroup } from '@/api/memories'
import type { Photo } from '@/types/photo'

const loading = ref(true)
const groups = ref<MemoryGroup[]>([])
const dateStr = ref('')
const columns = ref(window.innerWidth < 640 ? 3 : 6)

const prettyDate = computed(() => {
  const [mm, dd] = dateStr.value.split('-')
  return mm && dd ? `${Number(mm)} 月 ${Number(dd)} 日` : ''
})

// ── Viewer ───────────────────────────────────────────────────────────────────
const viewerPhoto = ref<Photo | null>(null)
const viewerList = ref<Photo[]>([])
const viewerIndex = ref(0)

function openViewer(list: Photo[], photo: Photo) {
  viewerList.value = list
  viewerIndex.value = list.findIndex((p) => p.id === photo.id)
  viewerPhoto.value = photo
}
function navigateViewer(delta: 1 | -1) {
  viewerIndex.value = Math.max(0, Math.min(viewerList.value.length - 1, viewerIndex.value + delta))
  viewerPhoto.value = viewerList.value[viewerIndex.value]
}

onMounted(async () => {
  try {
    const { data } = await memoriesApi.onThisDay()
    groups.value = data.groups
    dateStr.value = data.date
  } catch {
    ElMessage.error('加载回忆失败')
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.mem { max-width: 1100px; margin: 0 auto; padding: 24px 16px 64px; }
.mem-header h1 { font-size: 24px; font-weight: 700; margin: 0 0 4px; }
.mem-sub { color: var(--no-text-low, #888); font-size: 14px; margin: 0 0 28px; }

.mem-loading, .mem-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 10px; padding: 80px 16px; color: var(--no-text-low, #888); text-align: center;
}
.mem-empty p { font-size: 16px; color: var(--no-text, #ddd); margin: 6px 0 0; }
.mem-empty span { font-size: 13px; }

.mem-group { margin-bottom: 36px; }
.mem-group-head { display: flex; align-items: baseline; gap: 12px; margin-bottom: 12px; }
.mem-years-ago { font-size: 18px; font-weight: 700; color: var(--no-accent, #10b981); }
.mem-year { font-size: 13px; color: var(--no-text-low, #888); }

.mem-grid { display: grid; gap: 6px; }
.mem-cell {
  position: relative; aspect-ratio: 1; border-radius: 10px; overflow: hidden;
  cursor: pointer; background: var(--no-bg-card, #1a1a1a);
  transition: transform .15s;
}
.mem-cell:hover { transform: scale(1.02); }
.mem-cell img { width: 100%; height: 100%; object-fit: cover; }
.mem-video-badge {
  position: absolute; top: 6px; right: 6px; width: 26px; height: 26px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%; background: rgba(0,0,0,.55); color: #fff; pointer-events: none;
}
</style>
