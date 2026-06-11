<template>
  <div class="gl-root">
    <!-- ── Toast ────────────────────────────────────────────────── -->
    <Transition name="gl-toast">
      <div v-if="toast" class="gl-toast">
        <span class="gl-toast-dot" />
        <span>{{ toast }}</span>
      </div>
    </Transition>

    <!-- ── Page header ───────────────────────────────────────────── -->
    <div class="gl-page-header">
      <div>
        <h1 class="gl-page-title">照片库</h1>
        <p class="gl-page-subtitle">按拍摄时间自动归档，支持无缝缩放浏览。</p>
      </div>
      <div class="gl-density-control">
        <el-icon class="gl-density-icon"><Grid /></el-icon>
        <span class="gl-density-label">视图密度</span>
        <el-slider v-model="columns" :min="3" :max="12" :step="1" :show-tooltip="false" class="gl-density-slider" />
      </div>
    </div>

    <!-- ── Filter toolbar ──────────────────────────────────────── -->
    <div class="gl-toolbar">
      <div class="gl-toolbar-left">
        <el-select v-model="filter.sort_by" size="small" style="width:120px">
          <el-option label="拍摄时间" value="taken_at" />
          <el-option label="文件大小" value="file_size" />
          <el-option label="清晰度"   value="sharpness_score" />
        </el-select>

        <el-button-group size="small">
          <el-button :type="filter.order === 'desc' ? 'primary' : ''" @click="filter.order = 'desc'">↓</el-button>
          <el-button :type="filter.order === 'asc'  ? 'primary' : ''" @click="filter.order = 'asc'">↑</el-button>
        </el-button-group>

        <el-checkbox v-model="filter.only_duplicates" label="仅重复" size="small" />
      </div>

      <div class="gl-toolbar-right">
        <el-text type="info" size="small" class="gl-total-text">共 {{ photoStore.total }} 张</el-text>
      </div>
    </div>

    <!-- ── Timeline content ────────────────────────────────────── -->
    <div class="gl-content" ref="contentRef">
      <div v-if="photoStore.loading && photoStore.photos.length === 0" class="gl-loading">
        <span class="gl-spinner" />
        <span>加载中…</span>
      </div>

      <div v-else-if="sortedYears.length === 0" class="gl-empty">
        <el-empty description="照片库为空，请先运行扫描" />
      </div>

      <template v-else>
        <div
          v-for="year in sortedYears"
          :key="year"
          :id="'tl-' + year"
          class="gl-year-group"
        >
          <div class="gl-year-label">{{ year }}</div>

          <div
            v-for="month in sortedMonths(year)"
            :key="month"
            :id="'tl-' + year + '-' + month"
          >
            <div
              v-for="day in sortedDays(year, month)"
              :key="day"
            >
              <!-- Sticky day header -->
              <div class="gl-day-header">
                <span class="gl-day-title">{{ parseInt(month) }}月{{ parseInt(day) }}日</span>
                <span class="gl-day-count">
                  {{ year }}年 · {{ groupedPhotos[year][month][day].length }} 张
                </span>
              </div>

              <!-- Photo grid -->
              <div
                class="gl-photo-grid"
                :style="{ gridTemplateColumns: `repeat(${columns}, 1fr)` }"
              >
                <div
                  v-for="photo in groupedPhotos[year][month][day]"
                  :key="photo.id"
                  class="gl-photo-cell"
                  @click="openViewer(photo)"
                >
                  <img
                    :src="`/api/v1/thumbnails/${photo.id}?size=256`"
                    :alt="photo.file_name"
                    loading="lazy"
                    class="gl-thumb"
                    @error="onImgErr"
                  />
                  <!-- Hover overlay -->
                  <div class="gl-overlay">
                    <span class="gl-overlay-fname">{{ photo.file_name }}</span>
                    <div class="gl-overlay-badges">
                      <span class="gl-badge-score">{{ scoreLabel(photo) }}</span>
                      <span v-if="isRaw(photo)" class="gl-badge-raw">RAW</span>
                    </div>
                  </div>
                  <!-- Add to album button -->
                  <button
                    class="gl-add-album-btn"
                    title="加入相册"
                    @click.stop="openAddToAlbum(photo)"
                  >＋</button>
                  <!-- Add to diary button -->
                  <button
                    class="gl-add-diary-btn"
                    title="加入日记"
                    @click.stop="openAddToDiary(photo)"
                  >📔</button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Infinite scroll sentinel -->
        <div ref="sentinel" style="height:1px" />

        <!-- Loading more indicator -->
        <div v-if="photoStore.loading" class="gl-load-more">
          <span class="gl-spinner gl-spinner--sm" />
          加载更多…
        </div>
      </template>
    </div>

    <!-- ── Right timeline ruler ─────────────────────────────────── -->
    <div class="gl-ruler">
      <div class="gl-ruler-inner">
        <div
          v-for="(key, idx) in rulerKeys"
          :key="key"
          class="gl-ruler-item"
          @click="scrollToDate('tl-' + key.split('-')[0])"
        >
          <div class="gl-ruler-tip">
            {{ key.split('-')[0] }}年{{ parseInt(key.split('-')[1]) }}月
          </div>
          <span
            v-if="idx === 0 || rulerKeys[idx - 1].split('-')[0] !== key.split('-')[0]"
            class="gl-ruler-label"
          >
            {{ key.split('-')[0].slice(-2) }}
          </span>
          <div v-else class="gl-ruler-dot" />
        </div>
      </div>
    </div>

    <!-- ── Add to album picker ───────────────────────────────────── -->
    <el-dialog
      v-model="showAddAlbumDialog"
      title="加入相册"
      width="320px"
      destroy-on-close
    >
      <div v-if="albumStore.albums.length" class="gl-album-list">
        <button
          v-for="album in albumStore.albums"
          :key="album.id"
          class="gl-album-item"
          @click="quickAddToAlbum(album.id, album.title)"
        >
          <span class="gl-album-item-name">{{ album.title }}</span>
          <span class="gl-album-item-count">{{ album.photo_count }} 张</span>
        </button>
      </div>
      <div v-else class="gl-album-empty">暂无相册，请先在「我的相册」中创建。</div>
    </el-dialog>

    <!-- ── Add to diary picker ──────────────────────────────────── -->
    <el-dialog
      v-model="showAddDiaryDialog"
      title="加入日记"
      width="320px"
      destroy-on-close
    >
      <div class="gl-diary-picker">
        <p class="gl-diary-hint">选择要记录到哪一天的日记：</p>
        <el-date-picker
          v-model="diaryTargetDate"
          type="date"
          placeholder="选择日期"
          format="YYYY年MM月DD日"
          value-format="YYYY-MM-DD"
          style="width: 100%"
          :disabled-date="(d: Date) => d > new Date()"
        />
        <div class="gl-diary-actions">
          <el-button plain @click="showAddDiaryDialog = false">取消</el-button>
          <el-button
            type="primary"
            color="#34d399"
            class="gl-diary-confirm"
            :loading="addingToDiary"
            :disabled="!diaryTargetDate"
            @click="confirmAddToDiary"
          >
            加入日记
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- ── Image viewer ──────────────────────────────────────────── -->
    <ImageViewer
      :visible="!!viewerPhoto"
      :photo="viewerPhoto"
      :has-prev="viewerIndex > 0"
      :has-next="viewerIndex < photoStore.photos.length - 1"
      @close="closeViewer"
      @navigate="onNavigate"
      @soft-delete="onSoftDelete"
      @toast="showToast"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { usePhotoStore } from '@/stores/usePhotoStore'
import { useAlbumStore } from '@/stores/useAlbumStore'
import { diaryApi } from '@/api/diary'
import ImageViewer from '@/components/gallery/ImageViewer.vue'
import type { Photo } from '@/types/photo'
import type { PhotoListParams } from '@/types/photo'

// ── Store & filter ───────────────────────────────────────────────────
const photoStore = usePhotoStore()
const albumStore = useAlbumStore()

const filter = reactive<PhotoListParams>({
  sort_by: 'taken_at',
  order: 'desc',
  only_duplicates: false,
})

// ── Layout ───────────────────────────────────────────────────────────
const columns = ref(6)
const contentRef = ref<HTMLElement | null>(null)

// ── Toast ─────────────────────────────────────────────────────────────
const toast = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(msg: string) {
  toast.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 3500)
}

// ── Timeline grouping ─────────────────────────────────────────────────
/**
 * Group loaded photos into nested Record: year → month → day → Photo[]
 * Uses exif.taken_at when available, falls back to created_at.
 */
const groupedPhotos = computed<Record<string, Record<string, Record<string, Photo[]>>>>(() => {
  const g: Record<string, Record<string, Record<string, Photo[]>>> = {}
  for (const p of photoStore.photos) {
    const raw = p.exif?.taken_at ?? p.created_at
    const d = raw ? new Date(raw) : null
    if (!d || isNaN(d.getTime())) continue
    const year  = String(d.getFullYear())
    const month = String(d.getMonth() + 1).padStart(2, '0')
    const day   = String(d.getDate()).padStart(2, '0')
    if (!g[year])         g[year] = {}
    if (!g[year][month])  g[year][month] = {}
    if (!g[year][month][day]) g[year][month][day] = []
    g[year][month][day].push(p)
  }
  return g
})

const sortedYears = computed(() =>
  Object.keys(groupedPhotos.value).sort((a, b) => Number(b) - Number(a)),
)

function sortedMonths(year: string): string[] {
  return Object.keys(groupedPhotos.value[year] ?? {}).sort((a, b) => Number(b) - Number(a))
}

function sortedDays(year: string, month: string): string[] {
  return Object.keys(groupedPhotos.value[year]?.[month] ?? {}).sort((a, b) => Number(b) - Number(a))
}

// ── Ruler ─────────────────────────────────────────────────────────────
const rulerKeys = computed<string[]>(() => {
  const s = new Set<string>()
  for (const p of photoStore.photos) {
    const raw = p.exif?.taken_at ?? p.created_at
    const d = raw ? new Date(raw) : null
    if (!d || isNaN(d.getTime())) continue
    s.add(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
  }
  return [...s].sort((a, b) => b.localeCompare(a))
})

function scrollToDate(id: string) {
  const el = document.getElementById(id)
  if (el) {
    const y = el.getBoundingClientRect().top + window.scrollY - 80
    window.scrollTo({ top: y, behavior: 'smooth' })
  }
}

// ── Viewer ────────────────────────────────────────────────────────────
const viewerPhoto = ref<Photo | null>(null)
const viewerIndex = ref(-1)

function openViewer(photo: Photo) {
  viewerIndex.value = photoStore.photos.findIndex((p) => p.id === photo.id)
  viewerPhoto.value = photo
}

function closeViewer() {
  viewerPhoto.value = null
  viewerIndex.value = -1
}

function onNavigate(delta: 1 | -1) {
  const next = viewerIndex.value + delta
  if (next >= 0 && next < photoStore.photos.length) {
    viewerIndex.value = next
    viewerPhoto.value = photoStore.photos[next]
  }
}

// ── Add to album (from cell hover button) ─────────────────────────────
const addAlbumTarget = ref<Photo | null>(null)
const showAddAlbumDialog = ref(false)

function openAddToAlbum(photo: Photo) {
  addAlbumTarget.value = photo
  showAddAlbumDialog.value = true
  if (albumStore.albums.length === 0) albumStore.fetchAlbums()
}

async function quickAddToAlbum(albumId: number, albumTitle: string) {
  if (!addAlbumTarget.value) return
  await albumStore.addPhotosToAlbum(albumId, [addAlbumTarget.value.id])
  showToast(`已加入相册「${albumTitle}」`)
  showAddAlbumDialog.value = false
  addAlbumTarget.value = null
}

// ── Add to diary (from cell hover button) ────────────────────────────
const addDiaryTarget = ref<Photo | null>(null)
const showAddDiaryDialog = ref(false)
const diaryTargetDate = ref<string>('')
const addingToDiary = ref(false)

/**
 * Open the diary date-picker dialog.
 * Pre-fills the date from photo.taken_at if available, otherwise today.
 */
function openAddToDiary(photo: Photo) {
  addDiaryTarget.value = photo
  // Use photo's taken_at date as default (format YYYY-MM-DD)
  if (photo.taken_at) {
    diaryTargetDate.value = photo.taken_at.slice(0, 10)
  } else {
    const today = new Date()
    diaryTargetDate.value = today.toISOString().slice(0, 10)
  }
  showAddDiaryDialog.value = true
}

/**
 * Upsert the photo into the diary for the selected date.
 * Merges with any existing photos on that day (doesn't overwrite content).
 */
async function confirmAddToDiary() {
  if (!addDiaryTarget.value || !diaryTargetDate.value) return
  addingToDiary.value = true
  try {
    // Fetch existing diary for that date to preserve existing photo_ids
    let existingPhotoIds: number[] = []
    let existingMood: string = 'calm'
    let existingContent: string | null = null
    try {
      const { data } = await diaryApi.getByDate(diaryTargetDate.value)
      existingPhotoIds = data.photo_ids
      existingMood = data.mood
      existingContent = data.content
    } catch {
      // 404 = no diary yet for that date, that's fine
    }

    const photoId = addDiaryTarget.value.id
    const mergedIds = existingPhotoIds.includes(photoId)
      ? existingPhotoIds
      : [...existingPhotoIds, photoId]

    await diaryApi.save({
      diary_date: diaryTargetDate.value,
      content: existingContent,
      mood: existingMood as any,
      photo_ids: mergedIds,
    })

    const [year, month, day] = diaryTargetDate.value.split('-')
    showToast(`已加入 ${parseInt(month)}月${parseInt(day)}日 的日记`)
    showAddDiaryDialog.value = false
    addDiaryTarget.value = null
  } catch {
    ElMessage.error('加入日记失败，请重试')
  } finally {
    addingToDiary.value = false
  }
}

async function onSoftDelete(photoId: number) {
  await photoStore.softDelete(photoId)
  const remaining = photoStore.photos
  if (remaining.length === 0) {
    closeViewer()
  } else {
    const newIdx = Math.min(viewerIndex.value, remaining.length - 1)
    viewerIndex.value = newIdx
    viewerPhoto.value = remaining[newIdx]
  }
}

// ── Infinite scroll ───────────────────────────────────────────────────
const sentinel = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

onMounted(async () => {
  await photoStore.fetchPage(true)

  observer = new IntersectionObserver(
    (entries) => { if (entries[0].isIntersecting) photoStore.fetchNextPage() },
    { threshold: 0.1 },
  )
  if (sentinel.value) observer.observe(sentinel.value)
})

onUnmounted(() => {
  observer?.disconnect()
  if (toastTimer) clearTimeout(toastTimer)
})

// Re-fetch when filter changes
watch(filter, () => photoStore.setFilter({ ...filter }), { deep: true })

// ── Helpers ───────────────────────────────────────────────────────────
function isRaw(p: Photo): boolean {
  return ['ARW', 'CR3', 'CR2', 'NEF', 'RAF', 'DNG', 'ORF'].includes(p.file_ext?.toUpperCase() ?? '')
}

/** Returns AI quality score 0.0–10.0 based on sharpness */
function scoreLabel(p: Photo): string {
  const s = p.scores?.sharpness_score
  if (s == null) return 'N/A'
  return Math.min(10, (s / 3000) * 10).toFixed(1)
}

function onImgErr(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.opacity = '0.2'
}
</script>

<style scoped lang="scss">
/* ── Root: dark canvas ────────────────────────────────────────────── */
.gl-root {
  min-height: 100%;
  background: var(--no-bg-main);
  color: var(--no-text-primary);
  font-family: var(--no-font-sans);
  position: relative;
  padding-right: 56px; /* room for ruler */
}

/* ── Page header ─────────────────────────────────────────────────── */
.gl-page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.gl-page-title {
  font-size: 24px; font-weight: 600;
  letter-spacing: -0.02em; margin: 0 0 4px;
  color: var(--no-text-primary);
}
.gl-page-subtitle {
  font-size: 13px; color: var(--no-text-secondary); margin: 0;
}
.gl-density-control {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--no-bg-card);
  padding: 8px 14px;
  border-radius: var(--no-radius-btn);
  border: 1px solid var(--no-border-low);
}
.gl-density-icon { color: var(--no-text-secondary); }
.gl-density-label { font-size: 13px; color: var(--no-text-secondary); white-space: nowrap; }
.gl-density-slider { width: 100px; }

/* ── Toast ───────────────────────────────────────────────────────── */
.gl-toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1999;
  background: var(--no-bg-card);
  border: 1px solid var(--no-accent-border);
  color: var(--no-text-primary);
  padding: 9px 20px;
  border-radius: var(--no-radius-pill);
  font-size: 12px;
  font-family: monospace;
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
  white-space: nowrap;
}

.gl-toast-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--no-accent);
  animation: pulse 1.5s infinite;
}

.gl-toast-enter-active,
.gl-toast-leave-active { transition: all 0.2s ease; }
.gl-toast-enter-from,
.gl-toast-leave-to { transform: translate(-50%, 16px); opacity: 0; }

/* ── Toolbar ─────────────────────────────────────────────────────── */
.gl-toolbar {
  position: sticky;
  top: 0;
  z-index: 30;
  background: rgba(14, 15, 17, 0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--no-border-low);
  padding: 8px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.gl-toolbar-left,
.gl-toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── Content ─────────────────────────────────────────────────────── */
.gl-content {
  padding: 16px 16px 80px;
}

.gl-loading,
.gl-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 80px 20px;
  color: var(--no-text-muted);
  font-size: 13px;
}

/* ── Year group ──────────────────────────────────────────────────── */
.gl-year-group { margin-bottom: 40px; }

.gl-year-label {
  font-size: 36px;
  font-weight: 900;
  color: #3f3f46;
  letter-spacing: -0.04em;
  margin-bottom: 16px;
}

/* ── Day header ──────────────────────────────────────────────────── */
.gl-day-header {
  position: sticky;
  top: 44px;
  z-index: 20;
  background: rgba(14, 15, 17, 0.80);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  padding: 10px 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border-bottom: 1px solid var(--no-border-low);
  margin-bottom: 10px;
}

.gl-day-title {
  font-size: 15px;
  font-weight: 600;
}

.gl-day-count {
  font-size: 11px;
  color: var(--no-text-secondary);
  font-family: monospace;
}

/* ── Photo grid ──────────────────────────────────────────────────── */
.gl-photo-grid {
  display: grid;
  gap: 5px;
  margin-bottom: 20px;
}

.gl-photo-cell {
  position: relative;
  aspect-ratio: 1;
  border-radius: var(--no-radius-btn);
  overflow: hidden;
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;

  &:hover {
    border-color: var(--no-accent);
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4);
  }
}

.gl-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
  will-change: transform;

  .gl-photo-cell:hover & { transform: scale(1.06); }
}

.gl-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, rgba(0,0,0,.85), rgba(0,0,0,.15), transparent);
  opacity: 0;
  transition: opacity 0.2s;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: 7px;

  .gl-photo-cell:hover & { opacity: 1; }
}

.gl-overlay-fname {
  font-size: 9px;
  color: var(--no-text-primary);
  font-family: monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 3px;
}

.gl-overlay-badges { display: flex; gap: 3px; }

.gl-badge-score {
  font-size: 8px;
  font-weight: 700;
  padding: 1px 5px;
  background: var(--no-accent);
  color: var(--no-bg-main);
  border-radius: 3px;
}

.gl-badge-raw {
  font-size: 8px;
  font-weight: 700;
  padding: 1px 5px;
  border: 1px solid rgba(255,255,255,.4);
  color: #fff;
  border-radius: 3px;
}

/* ── Infinite scroll indicators ──────────────────────────────────── */
.gl-load-more {
  text-align: center;
  padding: 20px;
  color: var(--no-text-muted);
  font-size: 12px;
  font-family: monospace;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.gl-spinner {
  display: inline-block;
  width: 16px; height: 16px;
  border: 2px solid var(--no-border-low);
  border-top-color: var(--no-text-secondary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;

  &--sm { width: 12px; height: 12px; }
}

/* ── Ruler ───────────────────────────────────────────────────────── */
.gl-ruler {
  position: fixed;
  right: 4px;
  top: 80px;
  bottom: 24px;
  width: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.gl-ruler-inner {
  height: 85%;
  max-height: 75vh;
  width: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  padding: 8px 2px;
  background: rgba(21, 23, 26, 0.6);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid var(--no-border-low);
  border-radius: 22px;
}

.gl-ruler-item {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: 4px 0;
  cursor: pointer;

  &:hover .gl-ruler-dot { background: var(--no-accent); }
  &:hover .gl-ruler-label { color: var(--no-accent); }
  &:hover .gl-ruler-tip { opacity: 1; }
}

.gl-ruler-tip {
  position: absolute;
  right: calc(100% + 4px);
  padding: 2px 7px;
  background: var(--no-border-low);
  border-radius: 5px;
  font-size: 9px;
  white-space: nowrap;
  font-family: monospace;
  color: #fff;
  opacity: 0;
  transition: opacity 0.15s;
  pointer-events: none;
}

.gl-ruler-label {
  font-size: 9px;
  font-weight: 700;
  font-family: monospace;
  color: var(--no-text-primary);
  transition: color 0.15s;
}

.gl-ruler-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #3f3f46;
  transition: background 0.15s;
}

/* ── Add-to-album button on cell hover ───────────────────────────── */
.gl-add-album-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(52, 211, 153, 0.85);
  border: none;
  color: var(--no-bg-main);
  font-size: 15px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s, transform 0.15s;
  z-index: 5;

  .gl-photo-cell:hover & { opacity: 1; }
  &:hover { transform: scale(1.15); }
}

/* ── Add-to-diary button on cell hover ──────────────────────────── */
.gl-add-diary-btn {
  position: absolute;
  top: 34px;   /* below the album button */
  right: 6px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(99, 102, 241, 0.85);
  border: none;
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s, transform 0.15s;
  z-index: 5;

  .gl-photo-cell:hover & { opacity: 1; }
  &:hover { transform: scale(1.15); }
}

/* ── Diary date picker dialog ────────────────────────────────────── */
.gl-diary-picker {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.gl-diary-hint {
  font-size: 13px;
  color: var(--no-text-muted);
  margin: 0;
}

.gl-diary-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.gl-diary-confirm {
  color: var(--no-bg-main) !important;
}

/* ── Album picker dialog items ────────────────────────────────────── */
.gl-album-list { display: flex; flex-direction: column; gap: 4px; }

.gl-album-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--no-text-primary);
  transition: border-color 0.15s;

  &:hover { border-color: var(--no-accent); }
}

.gl-album-item-name { font-weight: 500; }

.gl-album-item-count {
  font-size: 11px;
  color: var(--no-text-muted);
  font-family: var(--no-font-mono);
}

.gl-album-empty {
  text-align: center;
  padding: 20px;
  font-size: 13px;
  color: var(--no-text-muted);
}

/* ── Keyframes ───────────────────────────────────────────────────── */
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
@keyframes spin   { to{transform:rotate(360deg)} }
</style>
