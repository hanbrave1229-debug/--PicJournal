<template>
  <div class="ad-root">
    <!-- Header -->
    <div class="ad-header">
      <button class="ad-back" @click="router.back()">
        <el-icon><ArrowLeft /></el-icon>
        <span>相册</span>
      </button>
      <div class="ad-header-info" v-if="albumStore.currentAlbum">
        <h1>{{ albumStore.currentAlbum.title }}</h1>
        <p v-if="albumStore.currentAlbum.description">{{ albumStore.currentAlbum.description }}</p>
      </div>
      <div class="ad-header-actions" v-if="albumStore.currentAlbum">
        <span class="soft-badge">{{ albumStore.currentAlbumTotal }} 张</span>
        <el-button
          v-if="selectedIds.size > 0"
          type="danger"
          plain
          size="small"
          :icon="Remove"
          @click="removeSelected"
        >
          移出相册 ({{ selectedIds.size }})
        </el-button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="albumStore.loadingPhotos && !albumStore.currentAlbumPhotos.length" class="ad-loading">
      <el-icon class="is-loading" size="24"><Loading /></el-icon>
    </div>

    <!-- Empty -->
    <div v-else-if="!albumStore.loadingPhotos && !albumStore.currentAlbumPhotos.length" class="ad-empty">
      <el-icon size="36"><PictureFilled /></el-icon>
      <p>这个相册还没有照片。</p>
      <p class="ad-empty-hint">在照片库中悬停任意照片，点击「加入相册」按钮即可添加。</p>
    </div>

    <!-- Photo grid -->
    <div v-else class="ad-grid" :style="{ '--cols': columns }">
      <div
        v-for="photo in albumStore.currentAlbumPhotos"
        :key="photo.id"
        class="ad-cell"
        :class="{ 'is-selected': selectedIds.has(photo.id) }"
        @click="toggleSelect(photo.id)"
        @dblclick="openViewer(photo)"
      >
        <img
          :src="`/api/v1/thumbnails/${photo.id}?size=256`"
          class="ad-thumb"
          loading="lazy"
        />
        <div class="ad-cell-check">
          <el-icon v-if="selectedIds.has(photo.id)" class="ad-check-icon"><Select /></el-icon>
        </div>
        <!-- Remove button on hover -->
        <button class="ad-remove-btn" @click.stop="removeSingle(photo.id)">
          <el-icon><Remove /></el-icon>
        </button>
        <!-- Set as cover button on hover -->
        <button
          class="ad-cover-btn"
          :class="{ 'is-current-cover': albumStore.currentAlbum?.cover_photo_id === photo.id }"
          :title="albumStore.currentAlbum?.cover_photo_id === photo.id ? '当前封面' : '设为封面'"
          @click.stop="setCover(photo.id)"
        >
          <el-icon><Picture /></el-icon>
        </button>
      </div>
    </div>

    <!-- Load more -->
    <div
      v-if="hasMore"
      ref="loadMoreTrigger"
      class="ad-load-more"
    >
      <el-icon v-if="albumStore.loadingPhotos" class="is-loading"><Loading /></el-icon>
    </div>

    <!-- ImageViewer -->
    <ImageViewer
      v-if="viewerPhoto"
      :photo="viewerPhoto"
      :photos="albumStore.currentAlbumPhotos"
      @close="viewerPhoto = null"
      @prev="navigateViewer(-1)"
      @next="navigateViewer(1)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Loading, Picture, PictureFilled, Remove, Select } from '@element-plus/icons-vue'
import { useAlbumStore } from '@/stores/useAlbumStore'
import ImageViewer from '@/components/gallery/ImageViewer.vue'
import type { Photo } from '@/types/photo'

const route = useRoute()
const router = useRouter()
const albumStore = useAlbumStore()

const albumId = computed(() => Number(route.params.id))
const columns = ref(5)

// ── Selection ──────────────────────────────────────────────────────────────────
const selectedIds = ref<Set<number>>(new Set())

function toggleSelect(id: number) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
  // Trigger reactivity
  selectedIds.value = new Set(selectedIds.value)
}

// ── Viewer ─────────────────────────────────────────────────────────────────────
const viewerPhoto = ref<Photo | null>(null)
const viewerIndex = ref(0)

function openViewer(photo: Photo) {
  viewerIndex.value = albumStore.currentAlbumPhotos.findIndex((p) => p.id === photo.id)
  viewerPhoto.value = photo
}

function navigateViewer(delta: number) {
  const photos = albumStore.currentAlbumPhotos
  viewerIndex.value = (viewerIndex.value + delta + photos.length) % photos.length
  viewerPhoto.value = photos[viewerIndex.value]
}

// ── Remove ─────────────────────────────────────────────────────────────────────
/** Set a photo as the album cover. */
async function setCover(photoId: number) {
  if (!albumStore.currentAlbum) return
  const isCurrent = albumStore.currentAlbum.cover_photo_id === photoId
  try {
    await albumStore.updateAlbum(albumId.value, {
      cover_photo_id: isCurrent ? null : photoId,
    })
    ElMessage.success(isCurrent ? '已取消封面' : '已设为封面')
  } catch {
    ElMessage.error('操作失败')
  }
}

async function removeSingle(photoId: number) {
  await albumStore.removePhotosFromAlbum(albumId.value, [photoId])
  selectedIds.value.delete(photoId)
  selectedIds.value = new Set(selectedIds.value)
  ElMessage.success('已从相册移除')
}

async function removeSelected() {
  const ids = [...selectedIds.value]
  await ElMessageBox.confirm(
    `将 ${ids.length} 张照片从相册移除？照片本身不会被删除。`,
    '移出相册',
    { confirmButtonText: '移出', cancelButtonText: '取消', type: 'warning' },
  )
  await albumStore.removePhotosFromAlbum(albumId.value, ids)
  selectedIds.value = new Set()
  ElMessage.success(`已移出 ${ids.length} 张`)
}

// ── Pagination (IntersectionObserver) ──────────────────────────────────────────
const page = ref(1)
const PAGE_SIZE = 60

const hasMore = computed(
  () => albumStore.currentAlbumPhotos.length < albumStore.currentAlbumTotal,
)

const loadMoreTrigger = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

async function loadMore() {
  if (albumStore.loadingPhotos || !hasMore.value) return
  page.value += 1
  await albumStore.fetchAlbumPhotos(albumId.value, page.value, PAGE_SIZE)
}

onMounted(async () => {
  // Reset and fetch
  albumStore.currentAlbumPhotos = []
  albumStore.currentAlbumTotal = 0
  page.value = 1
  await albumStore.fetchAlbumPhotos(albumId.value, 1, PAGE_SIZE)

  // Fetch album metadata if not already loaded
  if (!albumStore.currentAlbum || albumStore.currentAlbum.id !== albumId.value) {
    const idx = albumStore.albums.findIndex((a) => a.id === albumId.value)
    if (idx !== -1) {
      albumStore.currentAlbum = albumStore.albums[idx]
    } else {
      await albumStore.fetchAlbums()
      albumStore.currentAlbum = albumStore.albums.find((a) => a.id === albumId.value) ?? null
    }
  }

  // Intersection observer for infinite scroll
  observer = new IntersectionObserver(
    (entries) => { if (entries[0].isIntersecting) loadMore() },
    { threshold: 0.1 },
  )
  if (loadMoreTrigger.value) observer.observe(loadMoreTrigger.value)
})

onUnmounted(() => {
  observer?.disconnect()
})
</script>

<style scoped lang="scss">
.ad-root {
  min-height: 100%;
  color: var(--no-text-primary);
  font-family: var(--no-font-sans);
}

// ── Header ────────────────────────────────────────────────────────────────────
.ad-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.ad-back {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: var(--no-text-secondary);
  cursor: pointer;
  font-size: 13px;
  padding: 0;
  transition: color 0.15s;
  white-space: nowrap;

  &:hover { color: var(--no-accent); }
}

.ad-header-info {
  flex: 1;
  h1 { font-size: 20px; font-weight: 600; margin: 0 0 2px; letter-spacing: -0.02em; }
  p  { font-size: 12px; color: var(--no-text-secondary); margin: 0; }
}

.ad-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

// ── Loading / Empty ───────────────────────────────────────────────────────────
.ad-loading {
  display: flex;
  justify-content: center;
  padding: 80px;
  color: var(--no-text-muted);
}

.ad-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80px 20px;
  gap: 10px;
  text-align: center;
  color: var(--no-text-muted);

  p { margin: 0; font-size: 14px; }
}
.ad-empty-hint {
  font-size: 12px !important;
  max-width: 360px;
}

// ── Grid ──────────────────────────────────────────────────────────────────────
.ad-grid {
  display: grid;
  grid-template-columns: repeat(var(--cols, 5), 1fr);
  gap: 4px;
}

// ── Cell ──────────────────────────────────────────────────────────────────────
.ad-cell {
  position: relative;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  border-radius: 4px;
  cursor: pointer;
  border: 2px solid transparent;
  transition: border-color 0.15s;

  &:hover {
    border-color: rgba(52, 211, 153, 0.45);

    .ad-remove-btn { opacity: 1; }
  }

  &.is-selected {
    border-color: var(--no-accent);

    .ad-cell-check { opacity: 1; }
  }
}

.ad-thumb {
  width: 100%; height: 100%;
  object-fit: cover;
  display: block;
}

// ── Selection overlay ─────────────────────────────────────────────────────────
.ad-cell-check {
  position: absolute;
  inset: 0;
  background: rgba(52, 211, 153, 0.18);
  opacity: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  transition: opacity 0.15s;
}

.ad-check-icon {
  background: var(--no-accent);
  border-radius: 50%;
  padding: 4px;
  color: var(--no-bg-main);
  font-size: 14px;
}

// ── Remove button ─────────────────────────────────────────────────────────────
.ad-remove-btn {
  position: absolute;
  top: 6px; right: 6px;
  width: 28px; height: 28px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  border: none;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s, background 0.15s;
  font-size: 14px;

  &:hover { background: rgba(248, 113, 113, 0.75); }
}

// ── Set cover button ──────────────────────────────────────────────────────────
.ad-cover-btn {
  position: absolute;
  top: 6px; left: 6px;
  width: 28px; height: 28px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  border: none;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s, background 0.15s;
  font-size: 14px;

  &:hover { background: rgba(52, 211, 153, 0.75); }

  &.is-current-cover {
    opacity: 1;
    background: rgba(52, 211, 153, 0.85);
    color: var(--no-bg-main);
  }
}

// Show cover btn on hover (alongside remove btn)
.ad-cell:hover .ad-cover-btn:not(.is-current-cover) {
  opacity: 1;
}

// ── Load more sentinel ────────────────────────────────────────────────────────
.ad-load-more {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--no-text-muted);
  margin-top: 8px;
}
</style>
