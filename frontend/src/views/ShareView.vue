<template>
  <div class="sv">
    <div v-if="loading" class="sv-center">
      <el-icon class="is-loading" size="24"><Loading /></el-icon>
    </div>

    <div v-else-if="error" class="sv-center sv-error">
      <el-icon size="40"><WarningFilled /></el-icon>
      <p>{{ error }}</p>
    </div>

    <!-- Password gate -->
    <div v-else-if="meta && meta.needs_password && !unlocked" class="sv-center sv-gate">
      <el-icon size="38"><Lock /></el-icon>
      <h2>{{ meta.album_title }}</h2>
      <p>该相册受密码保护</p>
      <el-input
        v-model="password"
        type="password"
        placeholder="请输入访问密码"
        show-password
        class="sv-pw-input"
        @keyup.enter="unlock"
      />
      <el-button type="primary" :loading="verifying" @click="unlock">查看相册</el-button>
    </div>

    <!-- Gallery -->
    <div v-else-if="meta" class="sv-album">
      <header class="sv-header">
        <h1>{{ meta.album_title }}</h1>
        <span class="sv-count">{{ total }} 张照片</span>
      </header>
      <div class="sv-grid">
        <div v-for="p in photos" :key="p.id" class="sv-cell" @click="openViewer(p)">
          <img :src="`/api/v1/thumbnails/${p.id}?size=256`" loading="lazy" />
          <div v-if="p.media_type === 'video'" class="sv-video-badge">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          </div>
        </div>
      </div>
      <div v-if="photos.length < total" class="sv-more">
        <el-button :loading="loadingMore" @click="loadMore">加载更多</el-button>
      </div>
      <footer class="sv-footer">由 拾光手账 分享</footer>
    </div>

    <ImageViewer
      :visible="!!viewerPhoto"
      :photo="viewerPhoto"
      :has-prev="viewerIndex > 0"
      :has-next="viewerIndex < photos.length - 1"
      @close="viewerPhoto = null"
      @navigate="navigateViewer"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Loading, Lock, WarningFilled } from '@element-plus/icons-vue'
import ImageViewer from '@/components/gallery/ImageViewer.vue'
import { sharesApi, type PublicShareMeta } from '@/api/shares'
import type { Photo } from '@/types/photo'

const route = useRoute()
const token = route.params.token as string

const loading = ref(true)
const error = ref('')
const meta = ref<PublicShareMeta | null>(null)
const unlocked = ref(false)
const verifying = ref(false)
const password = ref('')

const photos = ref<Photo[]>([])
const total = ref(0)
const page = ref(1)
const loadingMore = ref(false)

const viewerPhoto = ref<Photo | null>(null)
const viewerIndex = ref(0)

function openViewer(p: Photo) {
  viewerIndex.value = photos.value.findIndex((x) => x.id === p.id)
  viewerPhoto.value = p
}
function navigateViewer(delta: 1 | -1) {
  viewerIndex.value = Math.max(0, Math.min(photos.value.length - 1, viewerIndex.value + delta))
  viewerPhoto.value = photos.value[viewerIndex.value]
}

async function loadPhotos(reset = false) {
  const { data } = await sharesApi.publicPhotos(token, password.value || null, page.value, 100)
  total.value = data.total
  photos.value = reset ? data.items : [...photos.value, ...data.items]
}

async function unlock() {
  verifying.value = true
  try {
    page.value = 1
    await loadPhotos(true)
    unlocked.value = true
  } catch (e: any) {
    error.value = ''
    if (e?.response?.status === 401) {
      // wrong password — stay on gate, show inline hint via ElMessage-less approach
      password.value = ''
      ;(await import('element-plus')).ElMessage.error('密码错误')
    } else {
      error.value = e?.response?.data?.detail ?? '加载失败'
    }
  } finally {
    verifying.value = false
  }
}

async function loadMore() {
  loadingMore.value = true
  try {
    page.value += 1
    await loadPhotos(false)
  } finally {
    loadingMore.value = false
  }
}

onMounted(async () => {
  try {
    const { data } = await sharesApi.publicMeta(token)
    meta.value = data
    if (!data.needs_password) {
      await loadPhotos(true)
      unlocked.value = true
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? '分享链接无效或已过期'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.sv { min-height: 100vh; background: var(--no-bg, #0a0a0a); color: var(--no-text, #eee); }
.sv-center {
  min-height: 100vh; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 14px; padding: 24px; text-align: center;
}
.sv-error { color: #f87171; }
.sv-gate h2 { font-size: 20px; margin: 4px 0 0; }
.sv-gate p { color: var(--no-text-low, #888); font-size: 14px; margin: 0; }
.sv-pw-input { max-width: 280px; }

.sv-album { max-width: 1100px; margin: 0 auto; padding: 28px 16px 64px; }
.sv-header { display: flex; align-items: baseline; gap: 12px; margin-bottom: 20px; }
.sv-header h1 { font-size: 24px; font-weight: 700; margin: 0; }
.sv-count { color: var(--no-text-low, #888); font-size: 14px; }
.sv-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 6px; }
.sv-cell {
  position: relative; aspect-ratio: 1; border-radius: 10px; overflow: hidden;
  cursor: pointer; background: var(--no-bg-card, #1a1a1a); transition: transform .15s;
}
.sv-cell:hover { transform: scale(1.02); }
.sv-cell img { width: 100%; height: 100%; object-fit: cover; }
.sv-video-badge {
  position: absolute; top: 6px; right: 6px; width: 26px; height: 26px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%; background: rgba(0,0,0,.55); color: #fff; pointer-events: none;
}
.sv-more { text-align: center; margin-top: 24px; }
.sv-footer { text-align: center; margin-top: 40px; color: var(--no-text-low, #666); font-size: 12px; }
</style>
