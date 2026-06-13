<template>
  <Teleport to="body">
    <Transition name="iv-fade">
      <div
        v-if="visible && photo"
        class="iv-overlay"
        @mousemove="onGlobalMove"
        @mouseup="endDrag"
        @mouseleave="endDrag"
      >
        <!-- ── Header ───────────────────────────────────────────── -->
        <header class="iv-header">
          <button class="iv-back-btn" @click="emit('close')">
            <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18"/>
            </svg>
            返回相册
          </button>

          <div class="iv-header-right">
            <span class="iv-time-label">{{ exifTime }}</span>

            <!-- Album / favourite dropdown -->
            <div class="iv-album-wrap" ref="albumRef">
              <button
                :class="['iv-icon-btn', liked && 'iv-icon-btn--liked']"
                title="添加到相册"
                @click.stop="toggleAlbum"
              >
                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z"/>
                </svg>
              </button>

              <div v-if="showAlbum" class="iv-album-dd" @click.stop>
                <div class="iv-album-dd-header">
                  <span>保存到相册</span>
                  <button v-if="liked" class="iv-album-unlike" @click.stop="removeLike">取消收藏</button>
                </div>
                <div class="iv-album-list custom-scroll">
                  <button
                    v-for="a in albums"
                    :key="a.id"
                    class="iv-album-item"
                    @click.stop="addToAlbum(a.id, a.title)"
                  >
                    <svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-19.5 0A2.25 2.25 0 002.25 15v2.25a2.25 2.25 0 002.25 2.25h15a2.25 2.25 0 002.25-2.25V15a2.25 2.25 0 00-2.25-2.25m-19.5 0h19.5"/>
                    </svg>
                    <span>{{ a.title }}</span>
                  </button>
                </div>
                <div class="iv-album-create-wrap">
                  <div v-if="creatingAlbum" class="iv-album-input-row">
                    <input
                      ref="albumInput"
                      v-model="newAlbumName"
                      class="iv-album-input"
                      placeholder="相册名称…"
                      @keyup.enter="submitAlbum"
                    />
                    <button class="iv-album-submit" @click="submitAlbum">✓</button>
                  </div>
                  <button v-else class="iv-album-new-btn" @click="startCreatingAlbum">
                    ＋ 创建并添加
                  </button>
                </div>
              </div>
            </div>

            <!-- More — toggles EXIF/AI sidebar -->
            <button
              :class="['iv-icon-btn', showInfo && 'iv-icon-btn--active']"
              title="更多信息"
              @click="showInfo = !showInfo"
            >
              <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <circle cx="12" cy="5" r=".75" fill="currentColor"/>
                <circle cx="12" cy="12" r=".75" fill="currentColor"/>
                <circle cx="12" cy="19" r=".75" fill="currentColor"/>
              </svg>
            </button>
          </div>
        </header>

        <!-- ── Prev / Next ──────────────────────────────────────── -->
        <button
          v-if="hasPrev"
          class="iv-nav iv-nav--left"
          @click.stop="emit('navigate', -1)"
        >
          <svg width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5"/>
          </svg>
        </button>

        <button
          v-if="hasNext"
          class="iv-nav iv-nav--right"
          :class="showInfo && 'iv-nav--right-shifted'"
          @click.stop="emit('navigate', 1)"
        >
          <svg width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5"/>
          </svg>
        </button>

        <!-- ── Canvas ───────────────────────────────────────────── -->
        <div
          :class="['iv-canvas', showInfo && 'iv-canvas--shifted']"
          @mousedown.prevent="startDrag"
          @dblclick="resetTransform"
        >
          <div
            class="iv-img-wrap"
            :style="{
              transform: `translate(${pos.x}px, ${pos.y}px) scale(${zoom}) rotate(${rotation}deg)`,
              transition: dragging ? 'none' : 'transform 0.2s cubic-bezier(0.2,0,0,1)',
            }"
          >
            <img
              :src="thumbUrl"
              :alt="photo.file_name"
              draggable="false"
              class="iv-img"
            />
          </div>

          <!-- Original mode label -->
          <Transition name="iv-tag">
            <div v-if="isOriginal" class="iv-orig-tag">
              无损原图模式 (RAW)
            </div>
          </Transition>
        </div>

        <!-- ── Bottom toolbar ───────────────────────────────────── -->
        <div :class="['iv-toolbar', showInfo && 'iv-toolbar--shifted']">
          <!-- Original toggle -->
          <button
            :class="['iv-tb-btn', isOriginal && 'iv-tb-btn--active']"
            @click="isOriginal = !isOriginal"
          >
            <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5z"/>
            </svg>
            {{ isOriginal ? '原图已显' : '查看原图' }}
          </button>
          <div class="iv-tb-sep" />

          <!-- Zoom in -->
          <button class="iv-tb-icon" title="放大" @click="changeZoom(0.5)">
            <svg width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607zM10.5 7.5v6m3-3h-6"/>
            </svg>
          </button>

          <!-- Zoom out -->
          <button class="iv-tb-icon" title="缩小" @click="changeZoom(-0.5)">
            <svg width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607zM7.5 10.5h6"/>
            </svg>
          </button>

          <!-- Rotate -->
          <button class="iv-tb-icon" title="旋转" @click="rotation = (rotation + 90) % 360">
            <svg width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"/>
            </svg>
          </button>

          <div class="iv-tb-sep" />

          <!-- Fullscreen -->
          <button class="iv-tb-icon" title="全屏" @click="toggleFullscreen">
            <svg width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75v4.5m0-4.5h-4.5m4.5 0L15 9m5.25 11.25v-4.5m0 4.5h-4.5m4.5 0L15 15"/>
            </svg>
          </button>

          <!-- Archive -->
          <button class="iv-tb-icon iv-tb-icon--archive" title="归档（从主时间轴隐藏）" @click="onArchive">
            <svg width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-.375c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v.375c0 .621.504 1.125 1.125 1.125z"/>
            </svg>
          </button>

          <!-- Delete -->
          <button class="iv-tb-icon iv-tb-icon--danger" title="移入回收站" @click="onDelete">
            <svg width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/>
            </svg>
          </button>

          <div class="iv-tb-sep" />

          <!-- Info sidebar toggle -->
          <button
            :class="['iv-tb-icon', showInfo && 'iv-tb-icon--active']"
            title="照片详情"
            @click="showInfo = !showInfo"
          >
            <svg width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 111.063.852l-.708 2.836a.75.75 0 001.063.852l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"/>
            </svg>
          </button>
        </div>

        <!-- ── Info sidebar ─────────────────────────────────────── -->
        <aside :class="['iv-sidebar', 'custom-scroll', showInfo && 'iv-sidebar--open']">
          <div class="iv-sb-header">
            <span>照片详情</span>
            <button class="iv-sb-close" @click="showInfo = false">✕</button>
          </div>

          <!-- Histogram simulation -->
          <div class="iv-sb-section">
            <div class="iv-sb-label">RGB 直方图分布</div>
            <div class="iv-sb-card">
              <div class="iv-histogram">
                <div
                  v-for="(h, i) in histogram"
                  :key="i"
                  class="iv-hist-bar"
                  :style="{ height: h + '%', opacity: 0.4 + (i % 5) * 0.1 }"
                />
              </div>
            </div>
          </div>

          <!-- Basic info -->
          <div class="iv-sb-section">
            <div class="iv-sb-card">
              <div class="iv-sb-fname">{{ photo.file_name }}</div>
              <div class="iv-sb-row">
                <span>拍摄时间</span>
                <span class="iv-sb-val">{{ exifTime }}</span>
              </div>
              <div class="iv-sb-row">
                <span>分辨率</span>
                <span class="iv-sb-good">{{ resFmt }}</span>
              </div>
              <div class="iv-sb-row">
                <span>文件大小</span>
                <span class="iv-sb-val">{{ formatBytes(photo.file_size) }}</span>
              </div>
              <div class="iv-sb-row">
                <span>格式</span>
                <span class="iv-sb-val">{{ photo.file_ext.toUpperCase() }}</span>
              </div>
            </div>
          </div>

          <!-- EXIF -->
          <div class="iv-sb-section">
            <div class="iv-sb-label">拍摄参数 EXIF</div>
            <div class="iv-sb-card">
              <div v-if="photo.exif?.camera_make" class="iv-sb-row">
                <span>相机</span>
                <span class="iv-sb-val">{{ photo.exif.camera_make }} {{ photo.exif.camera_model }}</span>
              </div>
              <div v-if="photo.exif?.aperture" class="iv-sb-row">
                <span>光圈</span>
                <span class="iv-sb-val">{{ photo.exif.aperture }}</span>
              </div>
              <div v-if="photo.exif?.shutter_speed" class="iv-sb-row">
                <span>快门</span>
                <span class="iv-sb-val">{{ photo.exif.shutter_speed }}</span>
              </div>
              <div v-if="photo.exif?.iso" class="iv-sb-row">
                <span>ISO</span>
                <span class="iv-sb-val">{{ photo.exif.iso }}</span>
              </div>
              <div v-if="photo.exif?.gps_lat" class="iv-sb-row">
                <span>GPS</span>
                <span class="iv-sb-val">{{ photo.exif.gps_lat?.toFixed(5) }}, {{ photo.exif.gps_lon?.toFixed(5) }}</span>
              </div>
              <div v-if="!photo.exif?.camera_make && !photo.exif?.aperture" class="iv-sb-empty">
                暂无 EXIF 数据
              </div>
            </div>
          </div>

          <!-- Location -->
          <div v-if="photo.city || photo.exif?.gps_lat" class="iv-sb-section">
            <div class="iv-sb-label">拍摄地点</div>
            <div class="iv-sb-card iv-sb-location">
              <div v-if="photo.city" class="iv-loc-city">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
                  <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
                  <circle cx="12" cy="9" r="2.5"/>
                </svg>
                <span>
                  <template v-if="photo.country && photo.country !== photo.city">{{ photo.country }} › </template>
                  <template v-if="photo.province && photo.province !== photo.city">{{ photo.province }} · </template>
                  <strong>{{ photo.city }}</strong>
                </span>
              </div>
              <div v-if="photo.exif?.gps_lat" class="iv-loc-coords">
                {{ photo.exif.gps_lat.toFixed(5) }}°N, {{ photo.exif.gps_lon!.toFixed(5) }}°E
              </div>
              <a
                v-if="photo.exif?.gps_lat"
                :href="`https://www.openstreetmap.org/?mlat=${photo.exif.gps_lat}&mlon=${photo.exif.gps_lon}#map=15/${photo.exif.gps_lat}/${photo.exif.gps_lon}`"
                target="_blank"
                rel="noopener"
                class="iv-loc-map-link"
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2" stroke-linecap="round">
                  <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/>
                  <polyline points="15 3 21 3 21 9"/>
                  <line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
                在地图中查看
              </a>
            </div>
          </div>

          <!-- AI caption & tags -->
          <div class="iv-sb-section">
            <div class="iv-sb-label">AI 智能理解</div>
            <div class="iv-sb-card">
              <template v-if="photo.ai_caption || photo.ai_tags?.length">
                <p v-if="photo.ai_caption" class="iv-sb-caption">{{ photo.ai_caption }}</p>
                <div v-if="photo.ai_tags?.length" class="iv-sb-tags">
                  <span
                    v-for="tag in photo.ai_tags"
                    :key="tag"
                    class="iv-sb-tag"
                  >#{{ tag }}</span>
                </div>
              </template>
              <div v-else class="iv-sb-empty iv-sb-empty--ai">
                <span>尚未打标</span>
                <small>前往「设置」开启 AI 打标后，此处将显示场景描述与关键词</small>
              </div>
            </div>
          </div>

          <!-- AI scores -->
          <div class="iv-sb-section">
            <div class="iv-sb-label">AI 评估数据</div>
            <div class="iv-sb-card">
              <div class="iv-sb-row">
                <span>综合美学评分</span>
                <span class="iv-sb-score">{{ aiScore }}</span>
              </div>
              <div class="iv-sb-row">
                <span>清晰度</span>
                <span :class="sharpScore >= 500 ? 'iv-sb-good' : 'iv-sb-warn'">
                  {{ sharpLabel }}
                  <small style="color:#71717a">({{ sharpScore?.toFixed(0) ?? 'N/A' }})</small>
                </span>
              </div>
              <div v-if="photo.scores?.exposure_score != null" class="iv-sb-row">
                <span>曝光</span>
                <span class="iv-sb-val">{{ (photo.scores.exposure_score * 100).toFixed(0) }}%</span>
              </div>
            </div>
          </div>
        </aside>

      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import type { Photo } from '@/types/photo'
import { formatBytes } from '@/utils/format'
import { useAlbumStore } from '@/stores/useAlbumStore'
import { archiveApi } from '@/api/archive'

const albumStore = useAlbumStore()

// ── Props / emits ────────────────────────────────────────────────────
const props = defineProps<{
  visible: boolean
  photo: Photo | null
  hasPrev: boolean
  hasNext: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'navigate', delta: 1 | -1): void
  (e: 'soft-delete', photoId: number): void
  (e: 'toast', msg: string): void
}>()

// ── Viewer state ─────────────────────────────────────────────────────
const isOriginal = ref(false)
const showInfo = ref(false)
const zoom = ref(1)
const rotation = ref(0)
const pos = ref({ x: 0, y: 0 })
const dragging = ref(false)
const dragStart = ref({ x: 0, y: 0 })
const histogram = ref<number[]>([])

// ── Album / favourite ─────────────────────────────────────────────────
const showAlbum = ref(false)
const creatingAlbum = ref(false)
const newAlbumName = ref('')
const albumRef = ref<HTMLElement | null>(null)
const albumInput = ref<HTMLInputElement | null>(null)
const likedIds = ref(new Set<number>())
const albums = computed(() => albumStore.albums)

const liked = computed(() => props.photo != null && likedIds.value.has(props.photo.id))

// ── Computed display ─────────────────────────────────────────────────
const thumbUrl = computed(() => {
  if (!props.photo) return ''
  // Default: 1080p thumbnail for a high-quality view without loading the raw file.
  // "查看原图" serves the raw file directly via the photos/file endpoint.
  return isOriginal.value
    ? `/api/v1/photos/${props.photo.id}/file`
    : `/api/v1/thumbnails/${props.photo.id}?size=1080`
})

const exifTime = computed(() => {
  const t = props.photo?.exif?.taken_at
  if (!t) return props.photo?.created_at?.slice(0, 19).replace('T', ' ') ?? ''
  return t.slice(0, 19).replace('T', ' ')
})

const resFmt = computed(() => {
  const p = props.photo
  if (!p?.width || !p?.height) return '未知'
  return `${p.width} × ${p.height}`
})

const sharpScore = computed(() => props.photo?.scores?.sharpness_score ?? null)

const sharpLabel = computed(() => {
  const s = sharpScore.value
  if (s == null) return '未知'
  if (s > 2000) return '极高'
  if (s > 500) return '高'
  if (s > 100) return '中等'
  return '轻微模糊'
})

const aiScore = computed(() => {
  const s = sharpScore.value
  if (s == null) return 'N/A'
  return Math.min(10, (s / 3000) * 10).toFixed(1)
})

// ── Transform ─────────────────────────────────────────────────────────
function startDrag(e: MouseEvent) {
  if (e.button !== 0) return
  dragging.value = true
  dragStart.value = { x: e.clientX - pos.value.x, y: e.clientY - pos.value.y }
}

function onGlobalMove(e: MouseEvent) {
  if (!dragging.value) return
  pos.value = { x: e.clientX - dragStart.value.x, y: e.clientY - dragStart.value.y }
}

function endDrag() {
  dragging.value = false
}

function resetTransform() {
  zoom.value = 1; rotation.value = 0; pos.value = { x: 0, y: 0 }
}

function changeZoom(delta: number) {
  zoom.value = Math.max(0.5, Math.min(8, zoom.value + delta))
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() =>
      emit('toast', '浏览器不支持全屏操作'))
  } else {
    document.exitFullscreen()
  }
}

function onDelete() {
  if (props.photo) {
    emit('soft-delete', props.photo.id)
    emit('toast', `已将照片「${props.photo.file_name}」移入回收站`)
  }
}

async function onArchive() {
  if (!props.photo) return
  try {
    await archiveApi.archive(props.photo.id)
    emit('toast', '已归档，主时间轴已隐藏')
    emit('close')
  } catch {
    emit('toast', '归档失败，请重试')
  }
}

// ── Album logic ───────────────────────────────────────────────────────
function showToast(msg: string) {
  emit('toast', msg)
}

function toggleAlbum() {
  if (!showAlbum.value && !liked.value && props.photo) {
    likedIds.value = new Set([...likedIds.value, props.photo.id])
    showToast('已添加至「我的收藏」')
  }
  showAlbum.value = !showAlbum.value
  creatingAlbum.value = false
}

function removeLike() {
  if (props.photo) likedIds.value.delete(props.photo.id)
  showAlbum.value = false
  showToast('已从收藏中移除')
}

async function addToAlbum(albumId: number, albumTitle: string) {
  if (!props.photo) return
  likedIds.value = new Set([...likedIds.value, props.photo.id])
  showAlbum.value = false
  await albumStore.addPhotosToAlbum(albumId, [props.photo.id])
  showToast(`已归档至相册「${albumTitle}」`)
}

function startCreatingAlbum() {
  creatingAlbum.value = true
  newAlbumName.value = ''
  nextTick(() => albumInput.value?.focus())
}

async function submitAlbum() {
  const name = newAlbumName.value.trim()
  if (!name) { creatingAlbum.value = false; return }
  const album = await albumStore.createAlbum(name)
  await addToAlbum(album.id, album.title)
  creatingAlbum.value = false
}

// Ensure albums are loaded when the dropdown is opened
watch(showAlbum, (v) => {
  if (v && albumStore.albums.length === 0) albumStore.fetchAlbums()
})

// ── Histogram simulation ──────────────────────────────────────────────
function genHistogram() {
  histogram.value = Array.from({ length: 38 }, () => Math.floor(20 + Math.random() * 80))
}

// ── Keyboard navigation ───────────────────────────────────────────────
function onKeyDown(e: KeyboardEvent) {
  if (!props.visible) return
  switch (e.key) {
    case 'Escape':     emit('close'); break
    case 'ArrowLeft':  if (props.hasPrev) emit('navigate', -1); break
    case 'ArrowRight': if (props.hasNext) emit('navigate', 1); break
  }
}

// ── Click outside album menu ──────────────────────────────────────────
function onDocClick(e: MouseEvent) {
  if (albumRef.value && !albumRef.value.contains(e.target as Node)) {
    showAlbum.value = false
    creatingAlbum.value = false
  }
}

// Reset state when photo changes
watch(() => props.photo?.id, () => {
  resetTransform()
  isOriginal.value = false
  genHistogram()
  showAlbum.value = false
  creatingAlbum.value = false
})

watch(() => props.visible, (v) => {
  if (v) genHistogram()
})

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  document.addEventListener('mousedown', onDocClick)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  document.removeEventListener('mousedown', onDocClick)
})
</script>

<style scoped lang="scss">
/* ── Overlay ──────────────────────────────────────────────────────── */
.iv-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  overflow: hidden;
  background: var(--no-bg-main);
  user-select: none;
  -webkit-user-select: none;
  color: var(--no-text-primary);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.iv-fade-enter-active,
.iv-fade-leave-active { transition: opacity 0.25s ease; }
.iv-fade-enter-from,
.iv-fade-leave-to { opacity: 0; }

/* ── Header ───────────────────────────────────────────────────────── */
.iv-header {
  position: absolute;
  top: 0;
  width: 100%;
  height: 72px;
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.8), transparent);
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.iv-back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: var(--no-radius-pill);
  background: rgba(26, 26, 30, 0.8);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid var(--no-border-low);
  color: var(--no-text-primary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
  &:hover { background: var(--no-border-low); color: #fff; }
}

.iv-header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.iv-time-label {
  font-size: 11px;
  font-family: monospace;
  color: var(--no-text-secondary);
}

.iv-icon-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(26, 26, 30, 0.8);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid var(--no-border-low);
  color: var(--no-text-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  &:hover { background: var(--no-border-low); color: #fff; }

  &--liked svg { fill: #f87171; stroke: #f87171; }
}

/* ── Album dropdown ───────────────────────────────────────────────── */
.iv-album-wrap { position: relative; }

.iv-album-dd {
  position: absolute;
  right: 0;
  top: calc(100% + 10px);
  width: 224px;
  background: rgba(18, 18, 20, 0.96);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--no-border-low);
  border-radius: var(--no-radius-card);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
  overflow: hidden;
  z-index: 50;
}

.iv-album-dd-header {
  padding: 8px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--no-border-low);
  font-size: 11px;
  color: var(--no-text-secondary);
}

.iv-album-unlike {
  background: none; border: none; cursor: pointer;
  color: #f87171; font-size: 11px;
  &:hover { color: #fff; }
}

.iv-album-list { max-height: 140px; overflow-y: auto; }

.iv-album-item {
  width: 100%;
  text-align: left;
  padding: 9px 14px;
  font-size: 12px;
  color: var(--no-text-primary);
  background: transparent;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: background 0.12s;
  &:hover { background: var(--no-border-low); }
}

.iv-album-create-wrap {
  border-top: 1px solid var(--no-border-low);
  padding: 6px;
}

.iv-album-input-row {
  display: flex;
  gap: 6px;
  padding: 2px;
}

.iv-album-input {
  flex: 1;
  background: var(--no-bg-card);
  border: 1px solid #3f3f46;
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 11px;
  color: #fff;
  outline: none;
  &:focus { border-color: var(--no-accent); }
}

.iv-album-submit {
  padding: 5px 8px;
  background: var(--no-accent);
  border: none;
  border-radius: 6px;
  color: var(--no-bg-main);
  font-weight: 700;
  cursor: pointer;
  font-size: 11px;
}

.iv-album-new-btn {
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  font-size: 12px;
  color: var(--no-accent);
  background: transparent;
  border: none;
  cursor: pointer;
  border-radius: 8px;
  &:hover { background: var(--no-bg-card); }
}

/* ── Nav buttons ──────────────────────────────────────────────────── */
.iv-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 40;
  padding: 10px;
  background: rgba(26, 26, 30, 0.4);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid var(--no-border-low);
  color: #fff;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  transition: all 0.15s;
  &:hover { background: rgba(39, 39, 42, 0.8); }

  &--left { left: 20px; }
  &--right { right: 20px; transition: right 0.3s ease; }
  &--right-shifted { right: 308px; }
}

/* ── Canvas ───────────────────────────────────────────────────────── */
.iv-canvas {
  flex: 1;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  transition: margin-right 0.3s ease;
  position: relative;
  &:active { cursor: grabbing; }
  &--shifted { margin-right: 288px; }
}

.iv-img-wrap {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  transform-origin: center center;
  will-change: transform;
}

.iv-img {
  max-width: 94%;
  max-height: 94%;
  object-fit: contain;
  pointer-events: none;
  filter: drop-shadow(0 24px 48px rgba(0, 0, 0, 0.6));
  user-select: none;
  -webkit-user-drag: none;
}

/* Original tag */
.iv-orig-tag {
  position: absolute;
  top: 76px;
  left: 50%;
  transform: translateX(-50%);
  padding: 3px 14px;
  background: rgba(74, 222, 128, 0.2);
  color: var(--no-accent);
  border: 1px solid rgba(74, 222, 128, 0.3);
  border-radius: var(--no-radius-pill);
  font-size: 11px;
  font-family: monospace;
  font-weight: 700;
  backdrop-filter: blur(8px);
}

.iv-tag-enter-active,
.iv-tag-leave-active { transition: opacity 0.2s ease; }
.iv-tag-enter-from,
.iv-tag-leave-to { opacity: 0; }

/* ── Toolbar ──────────────────────────────────────────────────────── */
.iv-toolbar {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 40;
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 7px;
  background: rgba(18, 18, 20, 0.88);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--no-border-low);
  border-radius: 16px;
  transition: margin-left 0.3s ease;

  &--shifted { margin-left: -144px; }
}

.iv-tb-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 12px;
  border-radius: 10px;
  background: transparent;
  border: none;
  color: #a1a1aa;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  &:hover { background: var(--no-border-low); color: #fff; }
  &--active { background: var(--no-accent) !important; color: var(--no-bg-main) !important; }
}

.iv-tb-icon {
  padding: 8px;
  border-radius: 10px;
  background: transparent;
  border: none;
  color: #a1a1aa;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  &:hover { background: var(--no-border-low); color: #fff; }
  &--danger:hover { background: rgba(248, 113, 113, 0.15); color: #f87171; }
  &--archive:hover { background: rgba(96, 165, 250, 0.15); color: #93c5fd; }
  &--active { background: var(--no-text-primary); color: var(--no-bg-main); }
}

.iv-tb-sep { width: 1px; height: 22px; background: var(--no-border-low); margin: 0 4px; }

/* ── Sidebar ──────────────────────────────────────────────────────── */
.iv-sidebar {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 288px;
  background: rgba(18, 18, 20, 0.96);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-left: 1px solid var(--no-border-low);
  z-index: 40;
  transform: translateX(100%);
  transition: transform 0.3s ease;
  overflow-y: auto;
  padding: 20px;
  font-size: 12px;

  &--open { transform: translateX(0); }
}

.iv-sb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 18px;
}

.iv-sb-close { cursor: pointer; color: var(--no-text-secondary); padding: 2px; background: none; border: none; &:hover { color: #fff; } }

.iv-sb-section { margin-bottom: 16px; }

.iv-sb-label {
  font-size: 10px;
  font-family: monospace;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #a1a1aa;
  margin-bottom: 6px;
}

.iv-sb-card {
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  border-radius: 10px;
  padding: 12px;
}

.iv-histogram {
  height: 64px;
  display: flex;
  align-items: flex-end;
  gap: 1px;
  overflow: hidden;
}

.iv-hist-bar {
  flex: 1;
  border-radius: 1px 1px 0 0;
  background: linear-gradient(to top, var(--no-text-secondary), var(--no-text-primary));
  min-height: 4px;
}

.iv-sb-fname {
  font-weight: 600;
  font-family: monospace;
  word-break: break-all;
  margin-bottom: 10px;
  font-size: 11px;
}

.iv-sb-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  color: #a1a1aa;
  font-family: monospace;
  gap: 8px;
  span:first-child { flex-shrink: 0; }
}

.iv-sb-val  { color: var(--no-text-primary); text-align: right; }
.iv-sb-good { color: var(--no-accent); font-weight: 600; }
.iv-sb-warn { color: #fbbf24; font-weight: 600; }
.iv-sb-score { color: var(--no-accent); font-size: 20px; font-weight: 700; }
.iv-sb-empty { color: var(--no-text-muted); font-size: 11px; text-align: center; padding: 6px 0; }

/* Location panel */
.iv-sb-location { display: flex; flex-direction: column; gap: 6px; }
.iv-loc-city {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--no-text-primary);
  svg { flex-shrink: 0; color: var(--el-color-primary); }
  strong { font-weight: 600; }
}
.iv-loc-coords {
  font-size: 11px;
  color: var(--no-text-muted);
  font-family: monospace;
  padding-left: 19px;
}
.iv-loc-map-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--el-color-primary);
  text-decoration: none;
  padding-left: 19px;
  &:hover { text-decoration: underline; }
}

/* AI caption & tags */
.iv-sb-caption {
  font-size: 13px;
  line-height: 1.6;
  color: var(--no-text-primary);
  margin: 0 0 10px;
  font-style: italic;
}

.iv-sb-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.iv-sb-tag {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 4px;
  background: rgba(52, 211, 153, 0.12);
  color: var(--no-accent);
  border: 1px solid rgba(52, 211, 153, 0.2);
  white-space: nowrap;
}

.iv-sb-empty--ai {
  display: flex;
  flex-direction: column;
  gap: 5px;
  align-items: center;
  padding: 10px 0;

  span { font-size: 12px; color: var(--no-text-muted); }
  small { font-size: 11px; color: var(--no-text-disabled); text-align: center; line-height: 1.4; }
}

/* ── Custom scrollbar ─────────────────────────────────────────────── */
.custom-scroll {
  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-track { background: transparent; }
  &::-webkit-scrollbar-thumb { background: var(--no-border-low); border-radius: 2px; }
}
</style>
