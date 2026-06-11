<template>
  <div class="dup-root">
    <!-- ── Toast notification ──────────────────────────────────────── -->
    <Transition name="toast-slide">
      <div v-if="toast" class="dup-toast">
        <span class="dup-toast-dot" />
        <span>{{ toast }}</span>
      </div>
    </Transition>

    <!-- ── Dashboard header ───────────────────────────────────────── -->
    <div class="dup-dash">
      <div class="dup-dash-left">
        <h1 class="dup-dash-title">
          分析结果面板
          <span class="dup-status-badge">
            <span class="dup-status-dot" />
            引擎就绪
          </span>
        </h1>
        <p class="dup-path">
          📂 /Volumes/personal_folder/Photos
        </p>
      </div>
      <div class="dup-stat-row">
        <div class="dup-stat-card">
          <div class="dup-stat-label">已扫描照片</div>
          <div class="dup-stat-val">{{ dupStore.groups.flatMap(g => g.photos).length || '–' }}</div>
        </div>
        <div class="dup-stat-card dup-stat-card--danger">
          <div class="dup-stat-label">可释放空间</div>
          <div class="dup-stat-val dup-stat-val--danger">{{ formatBytes(dupStore.totalReclaimable) }}</div>
        </div>
        <div class="dup-stat-card">
          <div class="dup-stat-label">相似 / 重复组</div>
          <div class="dup-stat-val dup-stat-val--warn">{{ dupStore.groups.length }}</div>
        </div>
      </div>
    </div>

    <!-- ── Batch control bar ──────────────────────────────────────── -->
    <div class="dup-toolbar">
      <div class="dup-toolbar-left">
        <label class="dup-check-label">
          <input
            v-model="allSelected"
            type="checkbox"
            class="dup-checkbox"
          />
          全选 {{ dupStore.groups.length }} 组
        </label>
        <span v-if="selectedIds.size > 0" class="dup-sel-badge">
          已选中 {{ selectedIds.size }} 组
        </span>
      </div>
      <div class="dup-toolbar-right">
        <button
          class="dup-run-btn"
          :disabled="running"
          @click="runDedup"
        >
          {{ running ? '⚙ 运行中…' : '⚙ 运行去重分析' }}
        </button>
        <button
          class="dup-del-btn"
          :disabled="selectedIds.size === 0"
          @click="batchExec"
        >
          🗑 一键清理选中组
        </button>
      </div>
    </div>

    <!-- ── Content ────────────────────────────────────────────────── -->
    <div class="dup-content">
      <!-- Loading -->
      <div v-if="dupStore.loading" class="dup-center">
        <span class="dup-spinner" />
        <span>加载中…</span>
      </div>

      <!-- Empty -->
      <div v-else-if="dupStore.groups.length === 0" class="dup-empty">
        <span class="dup-empty-icon">🛡</span>
        <h3>无照片去重分组</h3>
        <p>本地目录照片已全部保持最佳状态，暂无需要清理的相似文件。</p>
        <button class="dup-run-btn" style="margin-top:16px" @click="runDedup">运行去重分析</button>
      </div>

      <!-- Group list -->
      <div v-else class="dup-group-list">
        <div
          v-for="group in dupStore.groups"
          :key="group.id"
          class="dup-group-card"
        >
          <!-- Group header -->
          <div class="dup-group-head">
            <div class="dup-group-head-left">
              <input
                type="checkbox"
                class="dup-checkbox"
                :checked="selectedIds.has(group.id)"
                @change="toggleSelect(group.id)"
              />
              <span class="dup-sim-badge">
                ⚠ {{ typeLabel[group.group_type] }}
              </span>
              <span class="dup-group-id">组 ID: {{ group.id }}</span>
            </div>
            <div class="dup-group-head-right">
              <button
                class="dup-pk-btn"
                @click="openPK(group)"
              >
                ⚡ 高级 PK 对比
              </button>
              <button
                class="dup-exec-btn"
                @click="execRecommended(group)"
              >
                ✓ 执行推荐清理
              </button>
            </div>
          </div>

          <!-- Photo pair -->
          <div class="dup-photo-row">
            <div
              v-for="(photo, idx) in group.photos.slice(0, 2)"
              :key="photo.id"
              class="dup-photo-card"
            >
              <!-- Action tag -->
              <div
                :class="[
                  'dup-action-tag',
                  isRecommendedKeep(group, photo.id) ? 'dup-action-tag--keep' : 'dup-action-tag--del',
                ]"
              >
                {{ isRecommendedKeep(group, photo.id) ? '✓ 推荐保留' : '✕ 建议删除' }}
              </div>

              <!-- Hover PK button -->
              <button class="dup-hover-pk" @click="openPK(group)">
                🔍
              </button>

              <!-- RAW badge -->
              <span v-if="photo.file_ext.toUpperCase() === 'ARW' || photo.file_ext.toUpperCase() === 'CR3' || photo.file_ext.toUpperCase() === 'NEF'" class="dup-raw-badge">
                RAW
              </span>

              <!-- Thumbnail -->
              <div :class="['dup-thumb-wrap', !isRecommendedKeep(group, photo.id) && 'dup-thumb-wrap--dim']">
                <img
                  :src="thumbUrl(photo.id)"
                  :alt="photo.file_name"
                  class="dup-thumb"
                  loading="lazy"
                  @error="onImgError"
                />
              </div>

              <!-- Metadata -->
              <div class="dup-photo-meta">
                <div class="dup-photo-meta-top">
                  <span class="dup-fname" :title="photo.file_name">{{ photo.file_name }}</span>
                  <span
                    :class="[
                      'dup-score-badge',
                      isRecommendedKeep(group, photo.id) ? 'dup-score-badge--good' : 'dup-score-badge--bad',
                    ]"
                  >
                    {{ scoreLabel(photo) }}
                  </span>
                </div>
                <div class="dup-meta-grid">
                  <div class="dup-meta-item">
                    <span class="dup-meta-key">分辨率</span>
                    <span :class="['dup-meta-val', isRecommendedKeep(group, photo.id) ? 'dup-meta-val--good' : 'dup-meta-val--bad']">
                      {{ resFmt(photo) }}
                    </span>
                  </div>
                  <div class="dup-meta-item">
                    <span class="dup-meta-key">文件大小</span>
                    <span :class="['dup-meta-val', isRecommendedKeep(group, photo.id) ? '' : 'dup-meta-val--bad']">
                      {{ formatBytes(photo.file_size) }}
                    </span>
                  </div>
                  <div class="dup-meta-item">
                    <span class="dup-meta-key">清晰度</span>
                    <span :class="['dup-meta-val', isRecommendedKeep(group, photo.id) ? 'dup-meta-val--good' : 'dup-meta-val--bad']">
                      {{ sharpLabel(photo) }}
                    </span>
                  </div>
                  <div class="dup-meta-item">
                    <span class="dup-meta-key">拍摄时间</span>
                    <span class="dup-meta-val">{{ timeFmt(photo) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Infinite load hint -->
        <div class="dup-load-hint">
          <span class="dup-spinner dup-spinner--sm" />
          自动索引后台加载中…
        </div>
      </div>
    </div>

    <!-- ── PK Modal ────────────────────────────────────────────────── -->
    <PkCompareModal
      :visible="!!activePkGroup"
      :group="activePkGroup"
      @close="activePkGroup = null"
      @resolve="handlePkResolve"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDuplicateStore } from '@/stores/useDuplicateStore'
import PkCompareModal from '@/components/duplicate/PkCompareModal.vue'
import { formatBytes } from '@/utils/format'
import type { DuplicateGroup } from '@/types/duplicate'
import type { Photo } from '@/types/photo'

// ── Store ────────────────────────────────────────────────────────────
const dupStore = useDuplicateStore()

onMounted(() => dupStore.fetchGroups())

// ── Selection ─────────────────────────────────────────────────────────
const selectedIds = ref(new Set<number>())

const allSelected = computed<boolean>({
  get: () => dupStore.groups.length > 0 && selectedIds.value.size === dupStore.groups.length,
  set: (v: boolean) => {
    selectedIds.value = v ? new Set(dupStore.groups.map((g) => g.id)) : new Set()
  },
})

function toggleSelect(id: number) {
  const s = new Set(selectedIds.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  selectedIds.value = s
}

// ── Actions ───────────────────────────────────────────────────────────
const running = ref(false)

async function runDedup() {
  running.value = true
  try {
    await dupStore.runDedup()
    showToast('去重分析已启动，后台处理中…')
    setTimeout(() => dupStore.fetchGroups(), 3500)
  } finally {
    running.value = false
  }
}

async function execRecommended(group: DuplicateGroup) {
  if (!group.recommended_keep_id) {
    showToast('该组暂无智能推荐，请手动使用 PK 模式决策')
    return
  }
  const deleteIds = group.photos
    .filter((p) => p.id !== group.recommended_keep_id)
    .map((p) => p.id)

  await dupStore.resolve({
    group_id: group.id,
    keep_ids: [group.recommended_keep_id],
    delete_ids: deleteIds,
  })
  selectedIds.value.delete(group.id)
  showToast('已执行推荐清理方案，保留高质量原图！')
}

async function batchExec() {
  if (selectedIds.value.size === 0) return
  const ids = [...selectedIds.value]
  let count = 0
  for (const gid of ids) {
    const group = dupStore.groups.find((g) => g.id === gid)
    if (!group?.recommended_keep_id) continue
    const deleteIds = group.photos
      .filter((p) => p.id !== group.recommended_keep_id)
      .map((p) => p.id)
    await dupStore.resolve({
      group_id: group.id,
      keep_ids: [group.recommended_keep_id],
      delete_ids: deleteIds,
    })
    selectedIds.value.delete(gid)
    count++
  }
  showToast(`已批量清理 ${count} 组冗余照片！`)
}

// ── PK Modal ──────────────────────────────────────────────────────────
const activePkGroup = ref<DuplicateGroup | null>(null)

function openPK(group: DuplicateGroup) {
  activePkGroup.value = group
}

async function handlePkResolve(payload: { groupId: number; keepId: number; deleteIds: number[] }) {
  await dupStore.resolve({
    group_id: payload.groupId,
    keep_ids: [payload.keepId],
    delete_ids: payload.deleteIds,
  })
  activePkGroup.value = null
  selectedIds.value.delete(payload.groupId)
  showToast('决策完成：已保留目标照片，废片移入软删除区！')
}

// ── Toast ─────────────────────────────────────────────────────────────
const toast = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(msg: string) {
  toast.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 4000)
}

// ── Helpers ───────────────────────────────────────────────────────────
const typeLabel: Record<string, string> = {
  exact: '完全重复',
  similar: '相似照片',
  burst: '连拍序列',
}

function isRecommendedKeep(group: DuplicateGroup, photoId: number): boolean {
  if (group.recommended_keep_id == null) return group.photos[0]?.id === photoId
  return group.recommended_keep_id === photoId
}

function thumbUrl(photoId: number): string {
  return `/api/v1/thumbnails/${photoId}?size=256`
}

function onImgError(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.display = 'none'
}

function resFmt(p: Photo): string {
  if (p.width && p.height) return `${p.width} × ${p.height}`
  return '未知'
}

function sharpLabel(p: Photo): string {
  const s = p.scores?.sharpness_score
  if (s == null) return '未知'
  if (s > 2000) return '极高'
  if (s > 500) return '高'
  if (s > 100) return '中等'
  return '轻微模糊'
}

function scoreLabel(p: Photo): string {
  const s = p.scores?.sharpness_score
  if (s == null) return '美学分 N/A'
  const scaled = Math.min(10, (s / 3000) * 10)
  return `美学分 ${scaled.toFixed(1)}`
}

function timeFmt(p: Photo): string {
  const t = p.exif?.taken_at
  if (!t) return '未知'
  return t.replace('T', ' ').slice(0, 19)
}
</script>

<style scoped lang="scss">
/* ── Root: dark canvas ───────────────────────────────────────────── */
.dup-root {
  min-height: 100%;
  background: var(--no-bg-main);
  color: var(--no-text-primary);
  font-family: var(--no-font-sans);
  padding-bottom: 48px;
}

/* ── Toast ───────────────────────────────────────────────────────── */
.dup-toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 1999;
  background: var(--no-bg-card);
  border: 1px solid var(--no-accent-border);
  color: var(--no-text-primary);
  padding: 10px 18px;
  border-radius: 12px;
  font-size: 13px;
  font-family: monospace;
  display: flex;
  align-items: center;
  gap: 10px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}

.dup-toast-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--no-accent);
  animation: pulse 1.5s ease-in-out infinite;
}

.toast-slide-enter-active,
.toast-slide-leave-active { transition: all 0.2s ease; }
.toast-slide-enter-from,
.toast-slide-leave-to { transform: translateY(20px); opacity: 0; }

/* ── Dashboard ───────────────────────────────────────────────────── */
.dup-dash {
  background: transparent;
  border-bottom: none;
  padding: 0 0 8px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}

.dup-dash-title {
  font-size: 24px;
  font-weight: 600;
  letter-spacing: -0.02em;
  margin: 0;
  color: var(--no-text-primary);
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.dup-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 500;
  padding: 3px 10px;
  border-radius: var(--no-radius-pill);
  background: rgba(74, 222, 128, 0.1);
  color: var(--no-accent);
  border: 1px solid rgba(74, 222, 128, 0.2);
}

.dup-status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--no-accent);
  animation: pulse 2s ease-in-out infinite;
}

.dup-path {
  font-size: 11px;
  font-family: monospace;
  color: var(--no-accent);
  margin: 6px 0 0;
  background: var(--no-bg-card);
  padding: 5px 12px;
  border-radius: 8px;
  border: 1px solid var(--no-border-low);
  display: inline-block;
}

.dup-stat-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.dup-stat-card {
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  border-radius: 12px;
  padding: 14px 20px;
  min-width: 130px;
  flex: 1;

  &--danger { border-color: rgba(248, 113, 113, 0.2); }
}

.dup-stat-label {
  font-size: 12px;
  color: #a1a1aa;
}

.dup-stat-val {
  font-size: 26px;
  font-weight: 600;
  font-family: monospace;
  color: var(--no-text-primary);
  margin-top: 4px;

  &--danger { color: #f87171; }
  &--warn { color: #fbbf24; }
}

/* ── Toolbar ─────────────────────────────────────────────────────── */
.dup-toolbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(14, 15, 17, 0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--no-border-low);
  padding: 10px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}

.dup-toolbar-left,
.dup-toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dup-check-label {
  font-size: 13px;
  color: #a1a1aa;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  &:hover { color: var(--no-text-primary); }
}

.dup-checkbox {
  width: 15px;
  height: 15px;
  accent-color: var(--no-accent);
  cursor: pointer;
}

.dup-sel-badge {
  font-size: 11px;
  font-family: monospace;
  padding: 2px 8px;
  background: var(--no-border-low);
  border: 1px solid var(--no-border-low);
  border-radius: 6px;
  color: var(--no-text-secondary);
}

.dup-run-btn {
  font-size: 12px;
  padding: 7px 14px;
  border-radius: 10px;
  border: 1px solid #3f3f46;
  background: var(--no-border-low);
  color: var(--no-text-primary);
  cursor: pointer;
  transition: all 0.15s;
  &:hover:not(:disabled) { background: #3f3f46; }
  &:disabled { opacity: 0.4; cursor: not-allowed; }
}

.dup-del-btn {
  font-size: 12px;
  padding: 7px 14px;
  border-radius: 10px;
  border: 1px solid rgba(248, 113, 113, 0.3);
  background: rgba(248, 113, 113, 0.1);
  color: #f87171;
  cursor: pointer;
  transition: all 0.15s;
  &:hover:not(:disabled) { background: rgba(248, 113, 113, 0.18); }
  &:disabled { opacity: 0.3; cursor: not-allowed; }
}

/* ── Content ─────────────────────────────────────────────────────── */
.dup-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 20px;
}

.dup-center {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 60px;
  color: var(--no-text-muted);
  font-size: 13px;
}

.dup-spinner {
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2px solid var(--no-border-low);
  border-top-color: var(--no-text-secondary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;

  &--sm {
    width: 14px;
    height: 14px;
  }
}

.dup-empty {
  text-align: center;
  padding: 60px 20px;
  background: var(--no-bg-card);
  border: 1px dashed var(--no-border-low);
  border-radius: 16px;
}

.dup-empty-icon {
  font-size: 40px;
  display: block;
  margin-bottom: 12px;
}

.dup-empty h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 6px;
}

.dup-empty p {
  font-size: 13px;
  color: var(--no-text-secondary);
  margin: 0;
}

/* ── Group list ──────────────────────────────────────────────────── */
.dup-group-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.dup-group-card {
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  border-radius: 16px;
  overflow: hidden;
  transition: border-color 0.15s;

  &:hover { border-color: #3f3f46; }
}

/* ── Group header ─────────────────────────────────────────────────── */
.dup-group-head {
  background: var(--no-bg-card);
  padding: 12px 16px;
  border-bottom: 1px solid var(--no-border-low);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}

.dup-group-head-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dup-sim-badge {
  font-size: 11px;
  font-family: monospace;
  font-weight: 500;
  padding: 3px 9px;
  border-radius: 6px;
  background: rgba(251, 191, 36, 0.1);
  color: #fbbf24;
  border: 1px solid rgba(251, 191, 36, 0.2);
}

.dup-group-id {
  font-size: 11px;
  color: var(--no-text-muted);
  font-family: monospace;
}

.dup-group-head-right {
  display: flex;
  gap: 6px;
}

.dup-pk-btn {
  font-size: 11px;
  padding: 5px 12px;
  border-radius: 8px;
  border: 1px solid rgba(251, 191, 36, 0.25);
  background: rgba(251, 191, 36, 0.08);
  color: #fbbf24;
  cursor: pointer;
  transition: all 0.15s;
  &:hover { background: rgba(251, 191, 36, 0.15); }
}

.dup-exec-btn {
  font-size: 11px;
  padding: 5px 12px;
  border-radius: 8px;
  border: 1px solid #3f3f46;
  background: var(--no-border-low);
  color: var(--no-text-primary);
  cursor: pointer;
  transition: all 0.15s;
  &:hover { background: #3f3f46; }
}

/* ── Photo row ────────────────────────────────────────────────────── */
.dup-photo-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.dup-photo-card {
  padding: 16px;
  background: #131316;
  position: relative;
  border-right: 1px solid var(--no-border-low);

  &:last-child { border-right: none; }
}

/* Action tag */
.dup-action-tag {
  position: absolute;
  top: 24px;
  left: 24px;
  z-index: 10;
  font-size: 10px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 6px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);

  &--keep {
    background: rgba(74, 222, 128, 0.88);
    color: #051a0d;
  }

  &--del {
    background: rgba(248, 113, 113, 0.88);
    color: #fff;
  }
}

/* Hover PK button */
.dup-hover-pk {
  position: absolute;
  top: 24px;
  right: 24px;
  z-index: 10;
  font-size: 14px;
  padding: 6px 8px;
  border-radius: 10px;
  background: rgba(11, 11, 12, 0.8);
  border: 1px solid #3f3f46;
  color: var(--no-text-primary);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s;
}

.dup-photo-card:hover .dup-hover-pk { opacity: 1; }

/* RAW badge */
.dup-raw-badge {
  position: absolute;
  bottom: 80px;
  left: 24px;
  z-index: 10;
  font-size: 9px;
  font-weight: 700;
  font-family: monospace;
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

/* Thumbnail */
.dup-thumb-wrap {
  aspect-ratio: 4/3;
  border-radius: 10px;
  overflow: hidden;
  background: var(--no-bg-main);
  border: 1px solid var(--no-border-low);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.2s;

  &--dim { opacity: 0.65; }
  &:hover { opacity: 1 !important; }
}

.dup-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  will-change: transform;
  transform: translateZ(0);
}

/* Metadata */
.dup-photo-meta {
  margin-top: 12px;
}

.dup-photo-meta-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.dup-fname {
  font-size: 12px;
  font-weight: 500;
  font-family: monospace;
  color: var(--no-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 160px;
}

.dup-score-badge {
  font-size: 10px;
  font-family: monospace;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 6px;
  white-space: nowrap;
  flex-shrink: 0;

  &--good {
    background: rgba(74, 222, 128, 0.1);
    color: var(--no-accent);
    border: 1px solid rgba(74, 222, 128, 0.2);
  }

  &--bad {
    background: rgba(248, 113, 113, 0.1);
    color: #f87171;
    border: 1px solid rgba(248, 113, 113, 0.2);
  }
}

.dup-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 5px 12px;
  background: var(--no-bg-card);
  padding: 9px;
  border-radius: 8px;
  border: 1px solid rgba(34, 37, 42, 0.5);
}

.dup-meta-item {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.dup-meta-key {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--no-text-muted);
}

.dup-meta-val {
  font-size: 11px;
  font-family: monospace;
  color: var(--no-text-primary);

  &--good { color: var(--no-accent); }
  &--bad  { color: #f87171; }
}

/* ── Load hint ───────────────────────────────────────────────────── */
.dup-load-hint {
  text-align: center;
  padding: 32px;
  color: var(--no-text-muted);
  font-size: 12px;
  font-family: monospace;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

/* ── Keyframes ───────────────────────────────────────────────────── */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
