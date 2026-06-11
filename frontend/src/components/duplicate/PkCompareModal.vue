<template>
  <Teleport to="body">
    <Transition name="pk-fade">
      <div
        v-if="visible && group && group.photos.length >= 2"
        class="pk-overlay"
        @mousemove="onGlobalMove"
        @mouseup="stopDrag"
        @mouseleave="stopDrag"
      >
        <!-- ── Header ───────────────────────────────────────────── -->
        <header class="pk-header">
          <div class="pk-title-block">
            <span class="pk-icon-wrap">⚡</span>
            <div>
              <h2 class="pk-title">
                高级照片比对实验室
                <span class="pk-group-id">({{ group.id }})</span>
              </h2>
              <p class="pk-subtitle">
                智能相似度：
                <strong class="pk-sim">{{ similarityLabel }}</strong>
                <span class="pk-hint-text">| 按住左键拖拽可同步平移</span>
              </p>
            </div>
          </div>

          <div class="pk-controls">
            <!-- Layout toggle -->
            <div class="pk-btn-group">
              <button
                :class="['pk-ctl-btn', layout === 'h' && 'pk-ctl-btn--active']"
                title="左右排版"
                @click="layout = 'h'"
              >
                ⬛ 左右比对
              </button>
              <button
                :class="['pk-ctl-btn', layout === 'v' && 'pk-ctl-btn--active']"
                title="上下排版"
                @click="layout = 'v'"
              >
                ⬜ 上下比对
              </button>
            </div>

            <!-- Sync toggle -->
            <button
              :class="['pk-sync-btn', syncOn && 'pk-sync-btn--on']"
              @click="toggleSync"
            >
              <span>{{ syncOn ? '🔗' : '🔓' }} 操作随动同步</span>
            </button>

            <!-- Zoom slider -->
            <div class="pk-zoom-wrap">
              <span class="pk-zoom-icon">🔍</span>
              <input
                v-model.number="zoom"
                type="range"
                min="1"
                max="8"
                step="0.5"
                class="pk-zoom-slider"
              />
              <span class="pk-zoom-val">{{ zoom.toFixed(1) }}x</span>
            </div>

            <!-- Reset -->
            <button class="pk-ctl-btn" title="重置视口" @click="resetView">↺</button>

            <!-- Close -->
            <button class="pk-close-btn" title="退出比对" @click="emit('close')">✕</button>
          </div>
        </header>

        <!-- ── Body: two panes ─────────────────────────────────── -->
        <div :class="['pk-body', layout === 'h' ? 'pk-body--h' : 'pk-body--v']">

          <!-- Pane A: recommended keep -->
          <div
            class="pk-pane"
            @mousedown.prevent="startDrag($event, 'A')"
            @mousemove="onPaneMove($event, 'A')"
            @mouseleave="clearCrosshair"
          >
            <div class="pk-badge">
              <span class="pk-badge-tag pk-badge-tag--keep">照片 A (系统推荐保留)</span>
              <span class="pk-badge-score">美学分 {{ scoreLabel(photoA) }}</span>
            </div>

            <!-- Crosshair when hovering B, shown on A -->
            <div
              v-if="hoverSource === 'B' && hoverCoord"
              class="pk-crosshair"
              :style="{ left: hoverCoord.x + '%', top: hoverCoord.y + '%' }"
            >
              <div class="pk-ch-ring">
                <div class="pk-ch-dot" />
                <div class="pk-ch-line pk-ch-line--h" />
                <div class="pk-ch-line pk-ch-line--v" />
              </div>
            </div>

            <div class="pk-img-container" :style="transformStyleA">
              <img
                :src="thumbUrl(photoA)"
                :alt="photoA.file_name"
                draggable="false"
                class="pk-img"
              />
            </div>

            <div class="pk-meta-float">
              <div class="pk-meta-name">{{ photoA.file_name }}</div>
              <div class="pk-meta-grid">
                <span>尺寸: <em class="pk-good">{{ resFmt(photoA) }}</em></span>
                <span>大小: {{ fmtBytes(photoA.file_size) }}</span>
                <span>清晰度: <em class="pk-good">{{ sharpLabel(photoA) }}</em></span>
                <span>时间: {{ timeShort(photoA) }}</span>
              </div>
            </div>
          </div>

          <!-- Pane B: recommended delete -->
          <div
            class="pk-pane pk-pane--b"
            @mousedown.prevent="startDrag($event, 'B')"
            @mousemove="onPaneMove($event, 'B')"
            @mouseleave="clearCrosshair"
          >
            <div class="pk-badge">
              <span class="pk-badge-tag pk-badge-tag--del">照片 B (模糊/压缩版本)</span>
              <span class="pk-badge-score">美学分 {{ scoreLabel(photoB) }}</span>
            </div>

            <!-- Crosshair when hovering A, shown on B -->
            <div
              v-if="hoverSource === 'A' && hoverCoord"
              class="pk-crosshair"
              :style="{ left: hoverCoord.x + '%', top: hoverCoord.y + '%' }"
            >
              <div class="pk-ch-ring">
                <div class="pk-ch-dot" />
                <div class="pk-ch-line pk-ch-line--h" />
                <div class="pk-ch-line pk-ch-line--v" />
              </div>
            </div>

            <div class="pk-img-container" :style="transformStyleB">
              <img
                :src="thumbUrl(photoB)"
                :alt="photoB.file_name"
                draggable="false"
                class="pk-img pk-img--dim"
              />
            </div>

            <div class="pk-meta-float">
              <div class="pk-meta-name">{{ photoB.file_name }}</div>
              <div class="pk-meta-grid">
                <span>尺寸: <em class="pk-bad">{{ resFmt(photoB) }}</em></span>
                <span>大小: <em class="pk-bad">{{ fmtBytes(photoB.file_size) }}</em></span>
                <span>清晰度: <em class="pk-bad">{{ sharpLabel(photoB) }}</em></span>
                <span>时间: {{ timeShort(photoB) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- ── Footer: decision ─────────────────────────────────── -->
        <footer class="pk-footer">
          <div class="pk-footer-hint">
            <strong>💡 校验准则：</strong>
            照片 A 原生分辨率 {{ resFmt(photoA) }} 未压缩；
            照片 B 算法确认清晰度降低（{{ sharpLabel(photoB) }}）。推荐保留高画质版本。
          </div>
          <div class="pk-footer-actions">
            <button class="pk-keep-a-btn" @click="resolveKeepA">
              ✓ 保留 A，移入回收站 B
            </button>
            <button class="pk-keep-b-btn" @click="resolveKeepB">
              保留 B，移入回收站 A
            </button>
            <button class="pk-skip-btn" @click="emit('close')">
              保留全部 / 跳过
            </button>
          </div>
        </footer>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { DuplicateGroup } from '@/types/duplicate'
import type { Photo } from '@/types/photo'
import { formatBytes } from '@/utils/format'

// ── Props / emits ────────────────────────────────────────────────────
const props = defineProps<{
  visible: boolean
  group: DuplicateGroup | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  /** Resolve: keep keepId, soft-delete deleteIds */
  (e: 'resolve', payload: { groupId: number; keepId: number; deleteIds: number[] }): void
}>()

// ── Photo aliases ────────────────────────────────────────────────────
const photoA = computed<Photo>(() => props.group!.photos[0])
const photoB = computed<Photo>(() => props.group!.photos[1])

// ── PK state ─────────────────────────────────────────────────────────
const layout = ref<'h' | 'v'>('h')
const syncOn = ref(true)
const zoom = ref(1)

const offsetA = ref({ x: 0, y: 0 })
const offsetB = ref({ x: 0, y: 0 })

/** Crosshair: percentage coords inside the pane */
const hoverCoord = ref<{ x: number; y: number } | null>(null)
/** Which pane's mouse is active (crosshair shown on the OTHER pane) */
const hoverSource = ref<'A' | 'B' | null>(null)

// ── Drag ─────────────────────────────────────────────────────────────
const dragging = ref(false)
const dragSrc = ref<'A' | 'B'>('A')
const dragStart = ref({ x: 0, y: 0 })
const initOffA = ref({ x: 0, y: 0 })
const initOffB = ref({ x: 0, y: 0 })

function startDrag(e: MouseEvent, src: 'A' | 'B') {
  dragging.value = true
  dragSrc.value = src
  dragStart.value = { x: e.clientX, y: e.clientY }
  initOffA.value = { ...offsetA.value }
  initOffB.value = { ...offsetB.value }
}

function onGlobalMove(e: MouseEvent) {
  if (!dragging.value) return
  const dx = e.clientX - dragStart.value.x
  const dy = e.clientY - dragStart.value.y

  if (syncOn.value) {
    const nx = (dragSrc.value === 'A' ? initOffA.value.x : initOffB.value.x) + dx
    const ny = (dragSrc.value === 'A' ? initOffA.value.y : initOffB.value.y) + dy
    offsetA.value = { x: nx, y: ny }
    offsetB.value = { x: nx, y: ny }
  } else if (dragSrc.value === 'A') {
    offsetA.value = { x: initOffA.value.x + dx, y: initOffA.value.y + dy }
  } else {
    offsetB.value = { x: initOffB.value.x + dx, y: initOffB.value.y + dy }
  }
}

function stopDrag() {
  dragging.value = false
}

// ── Crosshair tracking ───────────────────────────────────────────────
function onPaneMove(e: MouseEvent, src: 'A' | 'B') {
  if (dragging.value) return
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  hoverCoord.value = {
    x: ((e.clientX - rect.left) / rect.width) * 100,
    y: ((e.clientY - rect.top) / rect.height) * 100,
  }
  hoverSource.value = src
}

function clearCrosshair() {
  if (!dragging.value) {
    hoverCoord.value = null
    hoverSource.value = null
  }
}

// ── Transform styles ─────────────────────────────────────────────────
const transformStyleA = computed(() => ({
  transform: `translate(${offsetA.value.x}px, ${offsetA.value.y}px) scale(${zoom.value})`,
  transition: dragging.value ? 'none' : 'transform 0.12s ease-out',
}))

const transformStyleB = computed(() => ({
  transform: `translate(${offsetB.value.x}px, ${offsetB.value.y}px) scale(${zoom.value})`,
  transition: dragging.value ? 'none' : 'transform 0.12s ease-out',
}))

// ── Controls ─────────────────────────────────────────────────────────
function toggleSync() {
  syncOn.value = !syncOn.value
  if (syncOn.value) {
    // Re-align B to A's position when re-enabling sync
    offsetB.value = { ...offsetA.value }
  }
}

function resetView() {
  zoom.value = 1
  offsetA.value = { x: 0, y: 0 }
  offsetB.value = { x: 0, y: 0 }
}

// ── Decisions ────────────────────────────────────────────────────────
function resolveKeepA() {
  emit('resolve', {
    groupId: props.group!.id,
    keepId: photoA.value.id,
    deleteIds: [photoB.value.id],
  })
}

function resolveKeepB() {
  emit('resolve', {
    groupId: props.group!.id,
    keepId: photoB.value.id,
    deleteIds: [photoA.value.id],
  })
}

// Reset state when group changes
watch(() => props.group?.id, resetView)

// ── Display helpers ───────────────────────────────────────────────────
/**
 * Build thumbnail URL for a photo.
 * Falls back to the original file path thumbnail if DB path is cached.
 */
function thumbUrl(photo: Photo): string {
  return `/api/v1/thumbnails/${photo.id}?size=1080`
}

/** Resolution string */
function resFmt(p: Photo): string {
  if (p.width && p.height) return `${p.width} × ${p.height}`
  return '未知'
}

/** Sharpness label from Laplacian variance score */
function sharpLabel(p: Photo): string {
  const s = p.scores?.sharpness_score
  if (s == null) return '未知'
  if (s > 2000) return '极高'
  if (s > 500) return '高'
  if (s > 100) return '中等'
  return '轻微模糊'
}

/** Aesthetic score label (sharpness as 0-10 scale) */
function scoreLabel(p: Photo): string {
  const s = p.scores?.sharpness_score
  if (s == null) return 'N/A'
  // Map Laplacian variance to 0-10 scale roughly
  const scaled = Math.min(10, (s / 3000) * 10)
  return scaled.toFixed(1)
}

/** Short time from EXIF */
function timeShort(p: Photo): string {
  const t = p.exif?.taken_at
  if (!t) return '未知'
  return t.split('T')[1]?.slice(0, 8) ?? t.slice(0, 10)
}

/** Format bytes (re-uses utility) */
function fmtBytes(n: number): string {
  return formatBytes(n)
}

/** Similarity label from phash hamming distance */
const similarityLabel = computed<string>(() => {
  if (!props.group) return '--'
  const a = props.group.photos[0]?.phash
  const b = props.group.photos[1]?.phash
  if (!a || !b || a.length !== b.length) {
    const typeMap: Record<string, string> = { exact: '完全重复', similar: '相似照片', burst: '连拍序列' }
    return typeMap[props.group.group_type] ?? props.group.group_type
  }
  let dist = 0
  for (let i = 0; i < a.length; i++) {
    const xor = (parseInt(a[i], 16) ^ parseInt(b[i], 16)) >>> 0
    for (let bit = 0; bit < 4; bit++) {
      if ((xor >> bit) & 1) dist++
    }
  }
  const pct = Math.max(0, Math.round((1 - dist / (a.length * 4)) * 100))
  return `${pct}%`
})
</script>

<style scoped lang="scss">
/* ── Overlay ─────────────────────────────────────────────────────── */
.pk-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  flex-direction: column;
  background: #09090a;
  color: #f4f4f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  user-select: none;
  -webkit-user-select: none;
}

/* Transition */
.pk-fade-enter-active,
.pk-fade-leave-active { transition: opacity 0.2s ease; }
.pk-fade-enter-from,
.pk-fade-leave-to { opacity: 0; }

/* ── Header ──────────────────────────────────────────────────────── */
.pk-header {
  flex-shrink: 0;
  background: #121214;
  border-bottom: 1px solid #1f1f23;
  padding: 12px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}

.pk-title-block {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pk-icon-wrap {
  font-size: 20px;
  padding: 6px;
  background: rgba(74, 222, 128, 0.1);
  border: 1px solid rgba(74, 222, 128, 0.25);
  border-radius: 8px;
  line-height: 1;
}

.pk-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.pk-group-id {
  font-size: 11px;
  color: #71717a;
  font-family: monospace;
  font-weight: 400;
}

.pk-subtitle {
  font-size: 11px;
  color: #a1a1aa;
  margin: 3px 0 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.pk-sim {
  color: #fbbf24;
  font-family: monospace;
  font-weight: 700;
}

.pk-hint-text {
  color: #52525b;
}

/* ── Controls ────────────────────────────────────────────────────── */
.pk-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.pk-btn-group {
  display: flex;
  background: #1a1a1e;
  border: 1px solid #27272a;
  border-radius: 8px;
  padding: 2px;
  gap: 2px;
}

.pk-ctl-btn {
  font-size: 11px;
  padding: 5px 10px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: #71717a;
  cursor: pointer;
  transition: all 0.15s;

  &:hover { color: #f4f4f5; }

  &--active {
    background: #27272a;
    color: #fbbf24;
  }
}

.pk-sync-btn {
  font-size: 11px;
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px solid #27272a;
  background: #1a1a1e;
  color: #71717a;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 4px;

  &--on {
    border-color: rgba(74, 222, 128, 0.35);
    background: rgba(74, 222, 128, 0.08);
    color: #4ade80;
  }
}

.pk-zoom-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #1a1a1e;
  border: 1px solid #27272a;
  border-radius: 8px;
  padding: 5px 10px;
}

.pk-zoom-icon { font-size: 12px; }

.pk-zoom-slider {
  width: 80px;
  accent-color: #fbbf24;
  cursor: pointer;
}

.pk-zoom-val {
  font-size: 11px;
  font-family: monospace;
  color: #fbbf24;
  min-width: 32px;
  text-align: right;
}

.pk-close-btn {
  font-size: 13px;
  padding: 5px 8px;
  border-radius: 6px;
  border: 1px solid rgba(248, 113, 113, 0.3);
  background: rgba(248, 113, 113, 0.08);
  color: #f87171;
  cursor: pointer;
  transition: all 0.15s;
  &:hover { background: rgba(248, 113, 113, 0.16); }
}

/* ── Body ────────────────────────────────────────────────────────── */
.pk-body {
  flex: 1;
  overflow: hidden;
  display: grid;
  background: #08080a;

  &--h {
    grid-template-columns: 1fr 1fr;
    .pk-pane:first-child { border-right: 1px solid #1f1f23; }
  }

  &--v {
    grid-template-rows: 1fr 1fr;
    .pk-pane:first-child { border-bottom: 1px solid #1f1f23; }
  }
}

/* ── Pane ────────────────────────────────────────────────────────── */
.pk-pane {
  position: relative;
  overflow: hidden;
  cursor: move;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pk-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.pk-badge-tag {
  font-size: 10px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 5px;
  font-family: monospace;

  &--keep {
    background: #4ade80;
    color: #051a0d;
  }

  &--del {
    background: #f87171;
    color: #fff;
  }
}

.pk-badge-score {
  font-size: 10px;
  font-family: monospace;
  padding: 3px 8px;
  border-radius: 5px;
  background: rgba(0, 0, 0, 0.65);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #a1a1aa;
}

/* ── Image container ─────────────────────────────────────────────── */
.pk-img-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  transform-origin: center center;
  will-change: transform;
}

.pk-img {
  max-width: 90%;
  max-height: 85%;
  object-fit: contain;
  border-radius: 6px;
  border: 1px solid #27272a;
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.5);
  pointer-events: none;
  user-select: none;
  -webkit-user-drag: none;

  &--dim { opacity: 0.72; }
}

/* ── Crosshair ───────────────────────────────────────────────────── */
.pk-crosshair {
  position: absolute;
  pointer-events: none;
  z-index: 30;
  transform: translate(-50%, -50%);
}

.pk-ch-ring {
  position: relative;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 1.5px dashed #fbbf24;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pk-ch-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #fbbf24;
  position: absolute;
}

.pk-ch-line {
  position: absolute;
  background: #fbbf24;

  &--h {
    width: 22px;
    height: 1px;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
  }

  &--v {
    width: 1px;
    height: 22px;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
  }
}

/* ── Meta float ──────────────────────────────────────────────────── */
.pk-meta-float {
  position: absolute;
  bottom: 12px;
  left: 12px;
  z-index: 20;
  max-width: 240px;
  background: rgba(18, 18, 20, 0.88);
  border: 1px solid #1f1f23;
  border-radius: 10px;
  padding: 9px 12px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.pk-meta-name {
  font-size: 11px;
  font-weight: 600;
  font-family: monospace;
  color: #f4f4f5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pk-meta-grid {
  margin-top: 5px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2px 12px;
  font-size: 10px;
  font-family: monospace;
  color: #71717a;
}

.pk-good { color: #4ade80; font-style: normal; font-weight: 600; }
.pk-bad  { color: #f87171; font-style: normal; font-weight: 600; }

/* ── Footer ──────────────────────────────────────────────────────── */
.pk-footer {
  flex-shrink: 0;
  background: #121214;
  border-top: 1px solid #1f1f23;
  padding: 14px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.pk-footer-hint {
  font-size: 11px;
  color: #71717a;
  max-width: 440px;
  line-height: 1.5;

  strong { color: #f4f4f5; }
}

.pk-footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pk-keep-a-btn {
  padding: 9px 20px;
  border-radius: 10px;
  border: none;
  background: #4ade80;
  color: #051a0d;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;
  &:hover { background: #22c55e; }
  &:active { transform: scale(0.97); }
}

.pk-keep-b-btn {
  padding: 9px 20px;
  border-radius: 10px;
  border: 1px solid #3f3f46;
  background: #1a1a1e;
  color: #f4f4f5;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  &:hover { background: #27272a; }
}

.pk-skip-btn {
  padding: 9px 14px;
  border: none;
  background: transparent;
  color: #71717a;
  font-size: 12px;
  cursor: pointer;
  transition: color 0.15s;
  &:hover { color: #f4f4f5; }
}
</style>
