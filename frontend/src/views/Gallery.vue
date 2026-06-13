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

        <!-- Media type filter -->
        <el-button-group size="small">
          <el-button
            :type="!filter.media_type ? 'primary' : ''"
            @click="filter.media_type = undefined"
          >全部</el-button>
          <el-button
            :type="filter.media_type === 'photo' ? 'primary' : ''"
            @click="filter.media_type = 'photo'"
          >📷 照片</el-button>
          <el-button
            :type="filter.media_type === 'video' ? 'primary' : ''"
            @click="filter.media_type = 'video'"
          >▶ 视频</el-button>
        </el-button-group>
      </div>

      <div class="gl-toolbar-right">
        <!-- Search bar (NL + Semantic modes) -->
        <div class="gl-nl-bar">
          <!-- Mode toggle -->
          <div class="gl-search-mode">
            <button
              class="gl-mode-btn"
              :class="{ 'is-active': searchMode === 'nl' }"
              title="AI 语义 SQL 搜索（需要 API Key）"
              @click="searchMode = 'nl'"
            >AI</button>
            <button
              class="gl-mode-btn"
              :class="{ 'is-active': searchMode === 'clip' }"
              title="CLIP 向量搜索（完全离线）"
              @click="searchMode = 'clip'"
            >向量</button>
          </div>
          <input
            v-model="nlQuery"
            class="gl-nl-input"
            :placeholder="searchMode === 'clip'
              ? '🔮 向量搜索：如「夕阳海边」「笑脸」（离线）…'
              : '✨ AI 搜索：如「春天的花」「2023年旅行」…'"
            @keydown.enter="runSearch"
            @keydown.escape="clearNLSearch"
          />
          <button
            class="gl-nl-btn"
            :class="{ 'is-loading': nlSearching }"
            :disabled="nlSearching"
            @click="runSearch"
          >
            {{ nlSearching ? '…' : '搜索' }}
          </button>
          <button
            v-if="nlResults !== null"
            class="gl-nl-clear"
            title="退出搜索"
            @click="clearNLSearch"
          >✕</button>
        </div>
        <el-text type="info" size="small" class="gl-total-text">共 {{ photoStore.total }} 张</el-text>

        <!-- Select / Import -->
        <el-button
          size="small"
          :type="selectMode ? 'primary' : ''"
          @click="toggleSelectMode"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.2" stroke-linecap="round" style="margin-right:4px">
            <polyline points="9 11 12 14 22 4"/>
            <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
          </svg>
          {{ selectMode ? `已选 ${selectedIds.length}` : '选择' }}
        </el-button>

        <el-button size="small" @click="showImportDialog = true">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.2" stroke-linecap="round" style="margin-right:4px">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          导入
        </el-button>
      </div>
    </div>

    <!-- ── Multi-select floating bar ─────────────────────────────── -->
    <Transition name="gl-selbar">
      <div v-if="selectMode" class="gl-select-bar">
        <span class="gl-select-bar-info">已选 <strong>{{ selectedIds.length }}</strong> 张</span>
        <el-button size="small" text @click="selectAll">全选</el-button>
        <el-button size="small" text @click="clearSelection">取消</el-button>
        <el-button
          size="small"
          type="primary"
          :disabled="!selectedIds.length"
          @click="showExportDialog = true"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.2" stroke-linecap="round" style="margin-right:4px">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          导出 ZIP
        </el-button>
        <el-button size="small" @click="toggleSelectMode">完成</el-button>
      </div>
    </Transition>

    <!-- ── NL Search results ──────────────────────────────────────── -->
    <Transition name="gl-search-fade">
      <div v-if="nlResults !== null" class="gl-search-results">
        <div class="gl-search-header">
          <span class="gl-search-label">
            🔍 「{{ nlQuery }}」— 找到 {{ nlResults.length }} 张
          </span>
          <button class="gl-search-close" @click="clearNLSearch">退出搜索</button>
        </div>
        <div
          v-if="nlResults.length > 0"
          class="gl-photo-grid gl-search-grid"
          :style="{ gridTemplateColumns: `repeat(${columns}, 1fr)` }"
        >
          <div
            v-for="photo in nlResults"
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
            <div class="gl-overlay">
              <span class="gl-overlay-fname">{{ photo.file_name }}</span>
            </div>
          </div>
        </div>
        <div v-else class="gl-search-empty">
          <el-empty description="没有匹配的照片，换个描述试试" />
        </div>
      </div>
    </Transition>

    <!-- ── Timeline content (hidden while in search mode) ───────── -->
    <div v-show="nlResults === null" class="gl-content" ref="contentRef">
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
            :id="`tl-${year}-${month}`"
          >
            <div
              v-for="day in sortedDays(year, month)"
              :key="day"
            >
              <!-- Sticky day header -->
              <div class="gl-day-header">
                <span class="gl-day-title">{{ parseInt(month) }}月{{ parseInt(day) }}日</span>
                <span
                  v-if="dayCityLabel[`${year}-${month}-${day}`]"
                  class="gl-day-city"
                  @click="$router.push({ name: 'places', query: { city: dayCityLabel[`${year}-${month}-${day}`].split(' · ').pop() } })"
                >
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                       stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
                    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
                    <circle cx="12" cy="9" r="2.5"/>
                  </svg>
                  {{ dayCityLabel[`${year}-${month}-${day}`] }}
                </span>
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
                  :class="{ 'gl-photo-cell--selected': selectedIds.includes(photo.id) }"
                  @click="selectMode ? togglePhotoSelect(photo.id, $event) : openViewer(photo)"
                >
                  <ProgressiveImage
                    :src="`/api/v1/thumbnails/${photo.id}?size=256`"
                    :alt="photo.file_name"
                    :thumbhash="photo.thumbhash"
                  />
                  <!-- Select mode checkbox -->
                  <div v-if="selectMode" class="gl-cell-check" @click.stop="togglePhotoSelect(photo.id, $event)">
                    <div :class="['gl-cell-checkbox', selectedIds.includes(photo.id) && 'gl-cell-checkbox--on']">
                      <svg v-if="selectedIds.includes(photo.id)" width="12" height="12"
                           viewBox="0 0 24 24" fill="currentColor">
                        <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                      </svg>
                    </div>
                  </div>
                  <!-- Hover overlay -->
                  <div class="gl-overlay">
                    <span class="gl-overlay-fname">{{ photo.file_name }}</span>
                    <div class="gl-overlay-badges">
                      <span class="gl-badge-score">{{ scoreLabel(photo) }}</span>
                      <span v-if="isRaw(photo)" class="gl-badge-raw">RAW</span>
                    </div>
                    <!-- AI tags (first 3) -->
                    <div v-if="photo.ai_tags?.length" class="gl-overlay-tags">
                      <span
                        v-for="tag in photo.ai_tags.slice(0, 3)"
                        :key="tag"
                        class="gl-overlay-tag"
                      >#{{ tag }}</span>
                    </div>
                    <!-- AI caption -->
                    <p v-if="photo.ai_caption" class="gl-overlay-caption">
                      {{ photo.ai_caption.length > 32 ? photo.ai_caption.slice(0, 32) + '…' : photo.ai_caption }}
                    </p>
                    <!-- Archive / Trash quick actions -->
                    <div class="gl-overlay-actions">
                      <button
                        class="gl-action-btn gl-action-archive"
                        title="归档（从主轴隐藏）"
                        @click.stop="handleArchive(photo)"
                      >归档</button>
                      <button
                        class="gl-action-btn gl-action-trash"
                        title="移入回收站"
                        @click.stop="handleTrashFromGallery(photo)"
                      >🗑</button>
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
                  <!-- Stack badge: shown only for stack covers -->
                  <div
                    v-if="photo.is_stack_cover && photo.stack_id"
                    class="gl-stack-badge"
                    title="连拍堆叠 — 点击打开挑选工作区"
                    @click.stop="$router.push(`/stacks/${photo.stack_id}`)"
                  >
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                         stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                      <rect x="2" y="7" width="20" height="14" rx="2"/>
                      <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
                      <line x1="12" y1="12" x2="12" y2="17"/>
                      <line x1="9.5" y1="14.5" x2="14.5" y2="14.5"/>
                    </svg>
                  </div>
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
          :class="['gl-ruler-item', activeRulerKey === key && 'is-active']"
          @click="scrollToDate(key)"
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

    <!-- ── Export dialog ──────────────────────────────────────────── -->
    <ExportDialog
      v-if="showExportDialog"
      v-model="showExportDialog"
      mode="photos"
      :photo-ids="selectedIds"
    />

    <!-- ── Import dialog ──────────────────────────────────────────── -->
    <ImportDialog
      v-if="showImportDialog"
      v-model="showImportDialog"
      :hide-tabs="['library']"
      @imported="() => photoStore.loadPhotos()"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { usePhotoStore } from '@/stores/usePhotoStore'
import { useAlbumStore } from '@/stores/useAlbumStore'
import { diaryApi } from '@/api/diary'
import { searchApi } from '@/api/search'
import { archiveApi } from '@/api/archive'
import ImageViewer from '@/components/gallery/ImageViewer.vue'
import ProgressiveImage from '@/components/gallery/ProgressiveImage.vue'
import ExportDialog from '@/components/transfer/ExportDialog.vue'
import ImportDialog from '@/components/transfer/ImportDialog.vue'
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

/**
 * 计算每日（year-month-day）出现频次最高的城市名。
 * 返回 "省·市" 格式（省和市相同时只显示市）。
 */
const dayCityLabel = computed<Record<string, string>>(() => {
  const result: Record<string, string> = {}
  for (const p of photoStore.photos) {
    if (!p.city) continue
    const raw = p.exif?.taken_at ?? p.created_at
    const d = raw ? new Date(raw) : null
    if (!d || isNaN(d.getTime())) continue
    const key = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
    // frequency count per city per day
    const label = p.province && p.province !== p.city
      ? `${p.province} · ${p.city}`
      : p.city
    if (!result[key]) {
      result[key] = label
    }
    // keep the most frequent: simple first-seen is good enough for daily grouping
  }
  return result
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

// ── Ruler + Scroll Spy ────────────────────────────────────────────────
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

const activeRulerKey = ref<string>('')

/** Get the actual scroll container (.app-main), not window */
function getScrollContainer(): HTMLElement | null {
  return document.querySelector('.app-main')
}

function scrollToDate(key: string) {
  // Try month-level element first, fall back to year
  const year = key.split('-')[0]
  const el = document.getElementById(`tl-${key}`) ?? document.getElementById(`tl-${year}`)
  const container = getScrollContainer()
  if (el && container) {
    // getBoundingClientRect is relative to viewport; container.scrollTop is absolute in container
    const y = el.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop - 80
    container.scrollTo({ top: y, behavior: 'smooth' })
    activeRulerKey.value = key
  }
}

/** Update the active ruler key based on scroll position. */
function onContentScroll() {
  for (const key of rulerKeys.value) {
    const year = key.split('-')[0]
    const el = document.getElementById(`tl-${key}`) ?? document.getElementById(`tl-${year}`)
    if (!el) continue
    const rect = el.getBoundingClientRect()
    if (rect.top <= 120) {
      activeRulerKey.value = key
    }
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
  if (photo.exif?.taken_at) {
    diaryTargetDate.value = photo.exif.taken_at.slice(0, 10)
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

// ── Archive action (from photo cell hover) ────────────────────────────
async function handleArchive(photo: Photo): Promise<void> {
  try {
    await archiveApi.archive(photo.id)
    // Remove from local store immediately
    photoStore.photos.splice(photoStore.photos.findIndex(p => p.id === photo.id), 1)
    showToast('已归档，主时间轴已隐藏')
  } catch {
    ElMessage.error('归档失败，请重试')
  }
}

async function handleTrashFromGallery(photo: Photo): Promise<void> {
  await photoStore.softDelete(photo.id)
  showToast('已移入回收站')
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

  const scrollEl = getScrollContainer()
  if (scrollEl) scrollEl.addEventListener('scroll', onContentScroll, { passive: true })
})

onUnmounted(() => {
  observer?.disconnect()
  if (toastTimer) clearTimeout(toastTimer)
  const scrollEl = getScrollContainer()
  if (scrollEl) scrollEl.removeEventListener('scroll', onContentScroll)
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

// ── Search (NL + CLIP) ────────────────────────────────────────────────
const nlQuery      = ref('')
const nlSearching  = ref(false)
const nlResults    = ref<Photo[] | null>(null)  // null = not in search mode
const nlResultClause = ref('')
const searchMode   = ref<'nl' | 'clip'>('nl')

// ── Multi-select & transfer ───────────────────────────────────────────────────
const selectMode       = ref(false)
const selectedIds      = ref<number[]>([])
const showExportDialog = ref(false)
const showImportDialog = ref(false)

function toggleSelectMode() {
  selectMode.value = !selectMode.value
  if (!selectMode.value) selectedIds.value = []
}

function togglePhotoSelect(id: number, event: MouseEvent) {
  event.stopPropagation()
  const idx = selectedIds.value.indexOf(id)
  if (idx === -1) selectedIds.value.push(id)
  else selectedIds.value.splice(idx, 1)
}

function selectAll() {
  selectedIds.value = photoStore.photos.map(p => p.id)
}

function clearSelection() {
  selectedIds.value = []
}

/** Unified dispatcher: routes to NL or CLIP search based on mode toggle */
async function runSearch(): Promise<void> {
  if (searchMode.value === 'clip') {
    await runClipSearch()
  } else {
    await runNLSearch()
  }
}

/** Run NL search; switch the view to search-result mode. */
async function runNLSearch(): Promise<void> {
  const q = nlQuery.value.trim()
  if (!q) { clearNLSearch(); return }

  nlSearching.value = true
  try {
    const { data } = await searchApi.nlSearch({ query: q, limit: 60 })
    nlResults.value = data.items
    nlResultClause.value = data.where_clause
    if (data.total === 0) ElMessage.info('没有找到匹配的照片')
  } catch (err: any) {
    const msg = err?.response?.data?.detail ?? 'AI 搜索失败，请检查 AI 配置'
    ElMessage.error(msg)
  } finally {
    nlSearching.value = false
  }
}

/** CLIP offline semantic search */
async function runClipSearch(): Promise<void> {
  const q = nlQuery.value.trim()
  if (!q) { clearNLSearch(); return }

  nlSearching.value = true
  try {
    const { data } = await searchApi.semanticSearch(q, 60)
    // Map SemanticSearchResult to Photo-like objects for reuse in grid
    nlResults.value = data.map((r) => ({
      id:            r.id,
      thumbnail_256: r.thumbnail_256,
      taken_at:      r.taken_at,
      ai_caption:    r.ai_caption,
      // fill required Photo fields with defaults so the grid renders
      file_path: '', file_name: '', file_ext: '', file_size: 0,
      width: null, height: null, md5_hash: null, phash: null,
      thumbnail_1080: null, is_deleted: false, duplicate_group_id: null,
      exif: { taken_at: r.taken_at, camera_make: null, camera_model: null,
              aperture: null, shutter_speed: null, iso: null, gps_lat: null, gps_lon: null },
      scores: { sharpness_score: null, exposure_score: null },
      ai_tags: [], thumbhash: null, country: null, province: null, city: null,
      is_archived: false, stack_id: null, is_stack_cover: false,
      created_at: '', updated_at: '',
    })) as any
    if (data.length === 0) ElMessage.info('没有找到语义相似的照片，请先触发 CLIP 嵌入')
  } catch (err: any) {
    const detail = err?.response?.data?.detail ?? ''
    if (detail.includes('不可用')) {
      ElMessage.warning('CLIP 模型未就绪，请在设置页触发嵌入后重试')
    } else {
      ElMessage.error('向量搜索失败')
    }
  } finally {
    nlSearching.value = false
  }
}

/** Clear search results and return to normal timeline. */
function clearNLSearch(): void {
  nlQuery.value = ''
  nlResults.value = null
  nlResultClause.value = ''
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

.gl-day-city {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: var(--el-color-primary);
  cursor: pointer;
  opacity: 0.85;
  transition: opacity 0.15s;

  svg { flex-shrink: 0; }

  &:hover { opacity: 1; text-decoration: underline; }
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

/* AI tags */
.gl-overlay-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: 5px;
}

.gl-overlay-tag {
  font-size: 8px;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(52, 211, 153, 0.25);
  color: #6ee7b7;
  white-space: nowrap;
}

/* AI caption */
.gl-overlay-caption {
  font-size: 9px;
  color: rgba(255, 255, 255, 0.75);
  margin: 4px 0 0;
  line-height: 1.4;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.gl-badge-score {
  font-size: 8px;
  font-weight: 700;
  padding: 1px 5px;
  background: var(--no-accent);
  color: var(--no-bg-main);
  border-radius: 3px;
}

// ── Archive / Trash hover action buttons ──────────────────────────────
.gl-overlay-actions {
  display: flex;
  gap: 5px;
  margin-top: 6px;
}

.gl-action-btn {
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  font-size: 10px;
  font-weight: 500;
  cursor: pointer;
  backdrop-filter: blur(4px);
  transition: all 150ms ease;

  &:hover {
    transform: translateY(-1px);
  }
}

.gl-action-archive {
  background: rgba(96, 165, 250, 0.18);
  color: #93c5fd;
  border-color: rgba(96, 165, 250, 0.3);

  &:hover {
    background: rgba(96, 165, 250, 0.35);
  }
}

.gl-action-trash {
  background: rgba(248, 113, 113, 0.15);
  color: #fca5a5;
  border-color: rgba(248, 113, 113, 0.3);

  &:hover {
    background: rgba(248, 113, 113, 0.35);
  }
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

  &.is-active .gl-ruler-dot { background: var(--no-accent); width: 8px; height: 8px; }
  &.is-active .gl-ruler-label { color: var(--no-accent); }
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

/* ── Stack badge ─────────────────────────────────────────────────── */
.gl-stack-badge {
  position: absolute;
  bottom: 6px;
  left: 6px;
  background: rgba(16, 185, 129, 0.88);
  border-radius: 4px;
  padding: 2px 5px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 5;
  transition: transform 0.15s;
  &:hover { transform: scale(1.12); }
}

/* ── Search mode toggle ──────────────────────────────────────────── */
.gl-search-mode {
  display: flex; border-radius: 5px; overflow: hidden;
  border: 1px solid var(--no-border-mid);
}
.gl-mode-btn {
  padding: 0 8px; height: 28px; background: var(--no-bg-card);
  border: none; color: var(--no-text-secondary); font-size: 11px;
  cursor: pointer; transition: background 0.15s, color 0.15s;
  &.is-active {
    background: var(--no-accent);
    color: #fff;
  }
  &:not(.is-active):hover { background: var(--no-border-low); }
}

/* ── NL Search bar ───────────────────────────────────────────────── */
.gl-nl-bar {
  display: flex;
  align-items: center;
  gap: 4px;
}

.gl-nl-input {
  width: 260px;
  height: 28px;
  padding: 0 10px;
  border-radius: 6px;
  border: 1px solid var(--no-border-mid);
  background: var(--no-bg-card);
  color: var(--no-text-primary);
  font-size: 12px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;

  &::placeholder { color: var(--no-text-disabled); }

  &:focus {
    border-color: #8b5cf6;
    box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.15);
  }
}

.gl-nl-btn {
  height: 28px;
  padding: 0 12px;
  border-radius: 6px;
  border: none;
  background: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%);
  background-size: 200% 200%;
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: filter 0.2s;
  white-space: nowrap;

  &:hover:not(:disabled) { filter: brightness(1.12); }
  &:disabled { opacity: 0.6; cursor: not-allowed; }

  &.is-loading { animation: ai-shimmer 1.5s ease infinite; }
}

@keyframes ai-shimmer {
  0%   { background-position: 0% 50%; }
  50%  { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

.gl-nl-clear {
  height: 28px;
  width: 28px;
  border-radius: 6px;
  border: 1px solid var(--no-border-mid);
  background: transparent;
  color: var(--no-text-muted);
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.15s;

  &:hover { background: var(--no-bg-hover); color: var(--no-text-primary); }
}

/* ── NL Search results panel ─────────────────────────────────────── */
.gl-search-results {
  margin-bottom: 16px;
}

.gl-search-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.12) 0%, rgba(236, 72, 153, 0.08) 100%);
  border: 1px solid rgba(139, 92, 246, 0.25);
}

.gl-search-label {
  font-size: 13px;
  color: var(--no-text-primary);
}

.gl-search-close {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 5px;
  border: 1px solid var(--no-border-mid);
  background: transparent;
  color: var(--no-text-muted);
  cursor: pointer;
  transition: background 0.15s;

  &:hover { background: var(--no-bg-hover); }
}

.gl-search-grid {
  margin-bottom: 0;
}

.gl-search-empty {
  padding: 40px 0;
}

/* Transition */
.gl-search-fade-enter-active,
.gl-search-fade-leave-active { transition: opacity 0.2s, transform 0.2s; }
.gl-search-fade-enter-from,
.gl-search-fade-leave-to { opacity: 0; transform: translateY(-8px); }

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

/* ── Multi-select ────────────────────────────────────────────────── */
.gl-photo-cell--selected::after {
  content: '';
  position: absolute;
  inset: 0;
  border: 3px solid var(--el-color-primary);
  border-radius: 2px;
  pointer-events: none;
  z-index: 2;
}

.gl-cell-check {
  position: absolute;
  top: 5px;
  left: 5px;
  z-index: 3;
}

.gl-cell-checkbox {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid rgba(255,255,255,0.9);
  background: rgba(0,0,0,0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  transition: background 0.15s, border-color 0.15s;

  &.gl-cell-checkbox--on {
    background: var(--el-color-primary);
    border-color: var(--el-color-primary);
  }
}

/* Select bar */
.gl-select-bar {
  position: sticky;
  bottom: 16px;
  z-index: 50;
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  border-radius: 12px;
  padding: 10px 16px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.14);
  margin: 16px auto 0;
  width: fit-content;
  max-width: 100%;
}

.gl-select-bar-info {
  font-size: 13px;
  color: var(--no-text-secondary);
  margin-right: 4px;
  strong { color: var(--no-text-primary); }
}

/* Select bar transition */
.gl-selbar-enter-active, .gl-selbar-leave-active { transition: opacity 0.2s, transform 0.2s; }
.gl-selbar-enter-from, .gl-selbar-leave-to { opacity: 0; transform: translateY(12px); }

/* ── Keyframes ───────────────────────────────────────────────────── */
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
@keyframes spin   { to{transform:rotate(360deg)} }

/* ── Mobile H5 ───────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .gl-root { padding: 0 6px 6px; }

  /* Toolbar wraps on mobile */
  .gl-toolbar {
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px 4px;
    top: 0;
  }

  .gl-search-row { width: 100%; }
  .gl-search-input { max-width: 100%; }

  /* Day header stacks city below count */
  .gl-day-header {
    flex-wrap: wrap;
    gap: 2px 8px;
    padding: 6px 4px;
    top: 56px; /* behind wrapped toolbar */
  }

  .gl-day-city { margin-left: 0; }

  /* Tighter grid on phone */
  .gl-photo-grid {
    grid-template-columns: repeat(3, 1fr) !important;
    gap: 2px;
  }

  /* Hide time ruler on mobile */
  .gl-time-ruler { display: none; }

  /* Scroll container fills narrower space */
  .gl-scroll { padding-right: 0; }
}
</style>
