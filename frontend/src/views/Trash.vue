<template>
  <div class="tr-root">
    <!-- Header -->
    <div class="tr-header">
      <div>
        <h1>回收站</h1>
        <p>软删除的照片，可以恢复或永久删除。</p>
      </div>
      <div class="tr-header-actions">
        <span v-if="albumStore.trashTotal" class="soft-badge soft-badge--warning">
          {{ albumStore.trashTotal }} 张待清理
        </span>
        <el-button
          v-if="albumStore.trashTotal"
          type="danger"
          plain
          size="small"
          :icon="Delete"
          :loading="emptying"
          @click="confirmEmpty"
        >
          清空回收站
        </el-button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="albumStore.loadingTrash && !albumStore.trashPhotos.length" class="tr-loading">
      <el-icon class="is-loading" size="24"><Loading /></el-icon>
    </div>

    <!-- Empty state -->
    <div v-else-if="!albumStore.loadingTrash && !albumStore.trashPhotos.length" class="tr-empty">
      <div class="tr-empty-icon">
        <el-icon size="36"><Delete /></el-icon>
      </div>
      <h2>回收站是空的</h2>
      <p>删除照片时，它们会先暂存于此。</p>
    </div>

    <!-- Photo grid -->
    <div v-else class="tr-grid">
      <div
        v-for="photo in albumStore.trashPhotos"
        :key="photo.id"
        class="tr-cell"
      >
        <!-- Thumbnail -->
        <div class="tr-thumb-wrap">
          <img
            :src="`/api/v1/thumbnails/${photo.id}?size=256`"
            class="tr-thumb"
            loading="lazy"
          />
          <!-- Actions overlay -->
          <div class="tr-actions">
            <button class="tr-btn tr-btn--restore" title="恢复" @click="restore(photo.id)">
              <el-icon><RefreshRight /></el-icon>
            </button>
            <button class="tr-btn tr-btn--delete" title="永久删除" @click="hardDelete(photo.id)">
              <el-icon><Delete /></el-icon>
            </button>
          </div>
        </div>
        <!-- Meta -->
        <div class="tr-meta">
          <span class="tr-fname">{{ photo.file_name }}</span>
          <span class="tr-date">{{ formatDeletedAt(photo.deleted_at) }}</span>
        </div>
      </div>
    </div>

    <!-- Load more -->
    <div v-if="hasMore" ref="loadMoreTrigger" class="tr-load-more">
      <el-icon v-if="albumStore.loadingTrash" class="is-loading"><Loading /></el-icon>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Loading, RefreshRight } from '@element-plus/icons-vue'
import { useAlbumStore } from '@/stores/useAlbumStore'

const albumStore = useAlbumStore()

const emptying = ref(false)
const page = ref(1)
const PAGE_SIZE = 60

const hasMore = computed(
  () => albumStore.trashPhotos.length < albumStore.trashTotal,
)

// ── Restore ─────────────────────────────────────────────────────────────────
async function restore(photoId: number) {
  await albumStore.restorePhoto(photoId)
  ElMessage.success('照片已恢复至照片库')
}

// ── Hard delete ──────────────────────────────────────────────────────────────
async function hardDelete(photoId: number) {
  await ElMessageBox.confirm(
    '永久删除后无法恢复，确认继续？',
    '永久删除',
    { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
  )
  await albumStore.hardDeletePhoto(photoId)
  ElMessage.success('已永久删除')
}

// ── Empty all ────────────────────────────────────────────────────────────────
async function confirmEmpty() {
  await ElMessageBox.confirm(
    `将永久删除回收站中所有 ${albumStore.trashTotal} 张照片，无法恢复。`,
    '清空回收站',
    { confirmButtonText: '全部删除', cancelButtonText: '取消', type: 'error' },
  )
  emptying.value = true
  try {
    const n = await albumStore.emptyTrash()
    ElMessage.success(`已清空 ${n} 张照片`)
  } finally {
    emptying.value = false
  }
}

// ── Infinite scroll ──────────────────────────────────────────────────────────
const loadMoreTrigger = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

async function loadMore() {
  if (albumStore.loadingTrash || !hasMore.value) return
  page.value += 1
  await albumStore.fetchTrash(page.value, PAGE_SIZE)
}

onMounted(async () => {
  albumStore.trashPhotos = []
  albumStore.trashTotal = 0
  page.value = 1
  await albumStore.fetchTrash(1, PAGE_SIZE)

  observer = new IntersectionObserver(
    (entries) => { if (entries[0].isIntersecting) loadMore() },
    { threshold: 0.1 },
  )
  if (loadMoreTrigger.value) observer.observe(loadMoreTrigger.value)
})

onUnmounted(() => observer?.disconnect())

// ── Helpers ──────────────────────────────────────────────────────────────────
/**
 * Format deleted_at timestamp to a human-readable relative or absolute string.
 */
function formatDeletedAt(ts: string | null): string {
  if (!ts) return ''
  const d = new Date(ts)
  const now = Date.now()
  const diff = now - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins} 分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days} 天前`
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<style scoped lang="scss">
.tr-root {
  min-height: 100%;
  color: var(--no-text-primary);
  font-family: var(--no-font-sans);
}

// ── Header ────────────────────────────────────────────────────────────────────
.tr-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;

  h1 { font-size: 22px; font-weight: 600; letter-spacing: -0.02em; margin: 0 0 4px; }
  p  { font-size: 13px; color: var(--no-text-secondary); margin: 0; }
}

.tr-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

// ── Loading / Empty ───────────────────────────────────────────────────────────
.tr-loading {
  display: flex;
  justify-content: center;
  padding: 80px;
  color: var(--no-text-muted);
}

.tr-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80px 20px;
  gap: 10px;
  text-align: center;
  color: var(--no-text-muted);

  h2 { font-size: 16px; font-weight: 500; margin: 0; color: var(--no-text-primary); }
  p  { font-size: 13px; margin: 0; }
}

.tr-empty-icon {
  width: 88px; height: 88px;
  border-radius: 50%;
  background: rgba(248, 113, 113, 0.08);
  display: flex; align-items: center; justify-content: center;
  color: #f87171;
  margin-bottom: 8px;
}

// ── Grid ──────────────────────────────────────────────────────────────────────
.tr-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}

// ── Cell ──────────────────────────────────────────────────────────────────────
.tr-cell {
  border-radius: 8px;
  overflow: hidden;
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  transition: border-color 0.15s;

  &:hover {
    border-color: rgba(248, 113, 113, 0.35);

    .tr-actions { opacity: 1; }
  }
}

.tr-thumb-wrap {
  position: relative;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  background: var(--no-bg-card-hover);
  opacity: 0.65;
}

.tr-thumb {
  width: 100%; height: 100%;
  object-fit: cover;
  display: block;
  filter: grayscale(25%);
}

// ── Action overlay ────────────────────────────────────────────────────────────
.tr-actions {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  opacity: 0;
  transition: opacity 0.2s;
}

.tr-btn {
  width: 36px; height: 36px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  transition: transform 0.15s;

  &:hover { transform: scale(1.12); }

  &--restore {
    background: rgba(52, 211, 153, 0.85);
    color: var(--no-bg-main);
  }

  &--delete {
    background: rgba(248, 113, 113, 0.85);
    color: #fff;
  }
}

// ── Meta ──────────────────────────────────────────────────────────────────────
.tr-meta {
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.tr-fname {
  font-size: 11px;
  font-family: var(--no-font-mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--no-text-secondary);
}

.tr-date {
  font-size: 10px;
  color: var(--no-text-muted);
}

// ── Load more ─────────────────────────────────────────────────────────────────
.tr-load-more {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--no-text-muted);
  margin-top: 8px;
}
</style>
