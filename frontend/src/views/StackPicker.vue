<template>
  <div class="sp-root">
    <!-- Header -->
    <div class="sp-header">
      <button class="sp-back" @click="$router.back()">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </button>
      <div class="sp-title-block">
        <h1 class="sp-title">连拍挑选</h1>
        <span class="sp-count">共 {{ photos.length }} 张</span>
      </div>
      <div class="sp-header-actions">
        <el-button size="small" @click="dissolveStack">解散堆叠</el-button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="sp-loading">
      <el-icon class="is-loading" size="32"><Loading /></el-icon>
    </div>

    <!-- Dual-panel picker -->
    <div v-else-if="photos.length" class="sp-layout">

      <!-- Left: filmstrip -->
      <div class="sp-strip" ref="stripRef">
        <div
          v-for="photo in photos"
          :key="photo.id"
          class="sp-strip-item"
          :class="{
            'is-selected': selectedId === photo.id,
            'is-cover': photo.is_stack_cover,
          }"
          @click="selectedId = photo.id"
        >
          <img
            :src="thumbUrl(photo)"
            class="sp-strip-thumb"
            loading="lazy"
          />
          <!-- Cover badge -->
          <div v-if="photo.is_stack_cover" class="sp-cover-badge" title="当前封面">
            <el-icon size="10"><StarFilled /></el-icon>
          </div>
          <!-- Sharpness bar -->
          <div class="sp-sharp-bar">
            <div
              class="sp-sharp-fill"
              :style="{ width: sharpnessPct(photo) + '%' }"
            />
          </div>
        </div>
      </div>

      <!-- Right: full-size preview -->
      <div class="sp-preview" v-if="selectedPhoto">
        <div class="sp-preview-img-wrap">
          <img
            :src="`/api/v1/photos/${selectedPhoto.id}/original`"
            class="sp-preview-img"
            :key="selectedPhoto.id"
          />
        </div>

        <!-- Info & actions -->
        <div class="sp-preview-meta">
          <div class="sp-preview-info">
            <span v-if="selectedPhoto.taken_at" class="sp-meta-item">
              <el-icon><Clock /></el-icon>
              {{ fmtDate(selectedPhoto.taken_at) }}
            </span>
            <span v-if="selectedPhoto.sharpness_score != null" class="sp-meta-item">
              <el-icon><View /></el-icon>
              清晰度 {{ selectedPhoto.sharpness_score.toFixed(0) }}
            </span>
            <span v-if="selectedPhoto.is_stack_cover" class="sp-meta-cover">
              <el-icon><StarFilled /></el-icon>
              当前封面
            </span>
          </div>

          <div class="sp-preview-actions">
            <el-button
              v-if="!selectedPhoto.is_stack_cover"
              type="primary"
              @click="setCover(selectedPhoto.id)"
              :loading="settingCover"
            >
              <el-icon><Star /></el-icon>
              设为封面
            </el-button>
            <el-button @click="unstackPhoto(selectedPhoto.id)">
              从堆叠中移除
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty -->
    <div v-else class="sp-empty">
      <p>堆叠为空或已解散</p>
      <el-button @click="$router.back()">返回</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Clock, Loading, Star, StarFilled, View } from '@element-plus/icons-vue'
import { stacksApi } from '@/api/search'
import type { StackPhoto } from '@/api/search'

const route  = useRoute()
const router = useRouter()

const stackId = route.params.stackId as string

const photos     = ref<StackPhoto[]>([])
const selectedId = ref<number | null>(null)
const loading    = ref(true)
const settingCover = ref(false)

const selectedPhoto = computed(() =>
  photos.value.find((p) => p.id === selectedId.value) ?? null
)

const maxSharpness = computed(() =>
  Math.max(...photos.value.map((p) => p.sharpness_score ?? 0), 1)
)

function sharpnessPct(photo: StackPhoto): number {
  return ((photo.sharpness_score ?? 0) / maxSharpness.value) * 100
}

function thumbUrl(photo: StackPhoto): string {
  if (photo.thumbnail_256) return `/api/v1/thumbnails/${photo.id}?size=256`
  return '/placeholder.png'
}

function fmtDate(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`
}

async function loadStack() {
  loading.value = true
  try {
    const { data } = await stacksApi.getStack(stackId)
    photos.value   = data
    selectedId.value = data.find((p) => p.is_stack_cover)?.id ?? data[0]?.id ?? null
  } catch {
    ElMessage.error('加载堆叠失败')
  } finally {
    loading.value = false
  }
}

async function setCover(photoId: number) {
  settingCover.value = true
  try {
    await stacksApi.setCover(stackId, photoId)
    photos.value = photos.value.map((p) => ({
      ...p,
      is_stack_cover: p.id === photoId,
    }))
    ElMessage.success('已设为封面')
  } catch {
    ElMessage.error('设置失败')
  } finally {
    settingCover.value = false
  }
}

async function unstackPhoto(photoId: number) {
  try {
    await stacksApi.unstackPhoto(photoId)
    photos.value = photos.value.filter((p) => p.id !== photoId)
    if (selectedId.value === photoId) {
      selectedId.value = photos.value[0]?.id ?? null
    }
    ElMessage.success('已从堆叠中移除')
    if (photos.value.length === 0) router.back()
  } catch {
    ElMessage.error('移除失败')
  }
}

async function dissolveStack() {
  try {
    await ElMessageBox.confirm(
      '解散堆叠后所有照片将变为独立照片，照片不会被删除。',
      '解散堆叠',
      { confirmButtonText: '解散', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  try {
    await stacksApi.dissolve(stackId)
    ElMessage.success('堆叠已解散')
    router.back()
  } catch {
    ElMessage.error('解散失败')
  }
}

onMounted(loadStack)
</script>

<style scoped lang="scss">
.sp-root {
  height: 100vh;
  display: flex; flex-direction: column;
  background: var(--no-bg-main);
  color: var(--no-text-primary);
}

.sp-header {
  display: flex; align-items: center; gap: 16px;
  padding: 14px 20px; border-bottom: 1px solid var(--no-border-low);
  flex-shrink: 0;
}
.sp-back {
  display: flex; align-items: center; gap: 4px;
  background: none; border: none; cursor: pointer;
  color: var(--no-text-secondary); font-size: 14px;
  &:hover { color: var(--no-text-primary); }
}
.sp-title-block { flex: 1; }
.sp-title { font-size: 17px; font-weight: 600; margin: 0; }
.sp-count { font-size: 12px; color: var(--no-text-muted); }

.sp-loading {
  flex: 1; display: flex; align-items: center; justify-content: center;
  color: var(--no-text-muted);
}

.sp-layout {
  flex: 1; display: flex; overflow: hidden; min-height: 0;
}

// ── Filmstrip (left) ─────────────────────────────────────────────────────────
.sp-strip {
  width: 160px; flex-shrink: 0;
  overflow-y: auto; border-right: 1px solid var(--no-border-low);
  display: flex; flex-direction: column; gap: 3px; padding: 8px;
  scrollbar-width: thin;
}
.sp-strip-item {
  position: relative; cursor: pointer; border-radius: 6px;
  border: 2px solid transparent; overflow: hidden;
  transition: border-color 0.15s;
  &.is-selected { border-color: var(--no-accent); }
  &.is-cover { box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.6); }
  &:hover:not(.is-selected) { border-color: var(--no-border-high); }
}
.sp-strip-thumb {
  width: 100%; aspect-ratio: 1/1; object-fit: cover; display: block;
}
.sp-cover-badge {
  position: absolute; top: 4px; right: 4px;
  background: rgba(251, 191, 36, 0.9); border-radius: 50%;
  width: 18px; height: 18px;
  display: flex; align-items: center; justify-content: center;
  color: #fff;
}
.sp-sharp-bar {
  height: 3px; background: rgba(255,255,255,0.15);
}
.sp-sharp-fill {
  height: 100%; background: var(--no-accent); transition: width 0.2s;
}

// ── Preview (right) ──────────────────────────────────────────────────────────
.sp-preview {
  flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0;
}
.sp-preview-img-wrap {
  flex: 1; display: flex; align-items: center; justify-content: center;
  background: #000; overflow: hidden; min-height: 0;
}
.sp-preview-img {
  max-width: 100%; max-height: 100%; object-fit: contain;
  display: block;
}
.sp-preview-meta {
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap;
  gap: 12px; padding: 12px 20px;
  border-top: 1px solid var(--no-border-low); flex-shrink: 0;
}
.sp-preview-info {
  display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
}
.sp-meta-item {
  display: flex; align-items: center; gap: 5px;
  font-size: 13px; color: var(--no-text-secondary);
}
.sp-meta-cover {
  display: flex; align-items: center; gap: 5px;
  font-size: 13px; color: #fbbf24; font-weight: 500;
}
.sp-preview-actions {
  display: flex; gap: 8px;
}

.sp-empty {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 12px;
  color: var(--no-text-muted); font-size: 15px;
}
</style>
