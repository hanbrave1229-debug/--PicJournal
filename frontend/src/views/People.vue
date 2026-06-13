<template>
  <div class="pp-root">

    <!-- ── Header ──────────────────────────────────────────────────────────── -->
    <div class="pp-header">
      <div>
        <h1 class="pp-title">人物</h1>
        <p class="pp-subtitle">基于本地 DBSCAN 聚类，面部特征不上传云端</p>
      </div>
      <div class="pp-header-actions">
        <el-checkbox v-model="showHidden" size="small" label="显示已隐藏" />
        <el-button size="small" :loading="personStore.loading" @click="personStore.fetchPersons(showHidden)">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button
          v-if="!personStore.running"
          type="primary" size="small"
          @click="runAnalysis"
        >
          <el-icon><VideoPlay /></el-icon>
          识别人脸
        </el-button>
        <div v-else class="pp-running">
          <span class="pp-spinner" /> 分析中…
        </div>
      </div>
    </div>

    <!-- ── Result banner ─────────────────────────────────────────────────── -->
    <Transition name="pp-fade">
      <div v-if="banner" class="pp-banner">
        <el-icon><CircleCheck /></el-icon>
        {{ banner }}
        <button class="pp-banner-close" @click="banner = ''">✕</button>
      </div>
    </Transition>

    <!-- ── Loading skeletons ─────────────────────────────────────────────── -->
    <div v-if="personStore.loading && !visiblePersons.length" class="pp-face-strip pp-skeleton-strip">
      <div v-for="i in 10" :key="i" class="pp-skel-circle" />
    </div>

    <!-- ── Empty state ───────────────────────────────────────────────────── -->
    <div v-else-if="!personStore.loading && !visiblePersons.length" class="pp-empty">
      <div class="pp-empty-icon">👤</div>
      <p class="pp-empty-text">尚未识别到人物</p>
      <p class="pp-empty-sub">点击「识别人脸」开始分析照片库</p>
      <el-button type="primary" @click="runAnalysis" :loading="personStore.running">
        开始识别
      </el-button>
    </div>

    <!-- ── Face strip ─────────────────────────────────────────────────────── -->
    <div v-else class="pp-face-strip" ref="stripRef">
      <div
        v-for="person in visiblePersons"
        :key="person.id"
        class="pp-face-item"
        :class="{
          'is-active':   activePerson?.id === person.id,
          'is-checked':  checkedIds.has(person.id),
          'is-hidden':   person.is_hidden,
          'is-locked':   person.is_locked,
        }"
        @click="onCircleClick(person)"
      >
        <!-- Circular avatar -->
        <div class="pp-circle">
          <img
            v-if="person.cover_path || person.cover_url"
            :src="person.cover_url || personsApi.cropUrl(person.cover_path)"
            :alt="person.name"
            class="pp-avatar"
            @error="onImgErr"
          />
          <div v-else class="pp-avatar-ph">
            <el-icon size="28"><User /></el-icon>
          </div>

          <!-- Checkbox overlay (top-right) -->
          <div
            class="pp-checkbox"
            :class="{ 'is-checked': checkedIds.has(person.id) }"
            @click.stop="toggleCheck(person.id)"
          >
            <el-icon v-if="checkedIds.has(person.id)" size="12"><Select /></el-icon>
          </div>

          <!-- Lock badge -->
          <div v-if="person.is_locked" class="pp-lock-badge">
            <el-icon size="9"><Lock /></el-icon>
          </div>
        </div>

        <!-- Name (click to edit inline) -->
        <div class="pp-face-name" @click.stop>
          <template v-if="editingId !== person.id">
            <span class="pp-name-text" @click="startEdit(person)">{{ person.name }}</span>
          </template>
          <template v-else>
            <input
              ref="nameInputRef"
              v-model="editingName"
              class="pp-name-input"
              maxlength="50"
              @keydown.enter="commitRename(person)"
              @keydown.escape="cancelEdit"
              @blur="commitRename(person)"
            />
          </template>
        </div>

        <!-- Preview photos (up to 4 thumbnails) -->
        <div v-if="person.preview_photos?.length" class="pp-preview-strip">
          <img
            v-for="url in person.preview_photos.slice(0, 4)"
            :key="url"
            :src="url"
            class="pp-preview-thumb"
            loading="lazy"
            @error="onImgErr"
          />
        </div>
      </div>

      <!-- Load more trigger -->
      <div v-if="personStore.hasMore" class="pp-load-more-item">
        <button class="pp-load-more-btn" :disabled="personStore.loadingMore" @click.stop="loadMore">
          <el-icon v-if="personStore.loadingMore" class="is-loading"><Loading /></el-icon>
          <span v-else>更多<br/>{{ personStore.totalPersons - personStore.persons.length }} 人</span>
        </button>
      </div>
    </div>

    <!-- ── Person photos section ─────────────────────────────────────────── -->
    <div v-if="activePerson" class="pp-photos-section">
      <!-- Section header -->
      <div class="pp-photos-header">
        <div class="pp-photos-meta">
          <span class="pp-photos-name">{{ activePerson.name }}</span>
          <span v-if="dateRange" class="pp-photos-range">· {{ dateRange }}</span>
        </div>
        <span class="pp-photos-count">共 {{ personStore.activePhotosTotal }} 项</span>
      </div>

      <!-- Loading -->
      <div v-if="personStore.loadingPhotos" class="pp-photos-loading">
        <el-icon class="is-loading" size="20"><Loading /></el-icon>
      </div>

      <!-- Photo grid -->
      <div v-else-if="personStore.activePhotos.length" class="pp-photos-grid">
        <div
          v-for="photo in personStore.activePhotos"
          :key="photo.id"
          class="pp-photo-cell"
          @click="openViewer(photo)"
        >
          <img
            :src="`/api/v1/thumbnails/${photo.id}?size=256`"
            class="pp-photo-thumb"
            loading="lazy"
          />
        </div>
      </div>

      <!-- No photos -->
      <div v-else class="pp-photos-empty">
        <el-icon size="24"><PictureFilled /></el-icon>
        <span>该人物暂无照片</span>
      </div>
    </div>

    <!-- ── Bottom action bar (multi-select) ─────────────────────────────── -->
    <Transition name="pp-bar">
      <div v-if="checkedIds.size > 0" class="pp-action-bar">
        <!-- Cancel -->
        <button class="pp-bar-cancel" @click="clearChecked">
          <el-icon><Close /></el-icon>
        </button>
        <span class="pp-bar-count">选中 {{ checkedIds.size }} 项</span>

        <div class="pp-bar-actions">
          <!-- Hide / Unhide -->
          <button class="pp-bar-btn" :title="allCheckedHidden ? '取消隐藏' : '隐藏'" @click="batchHide">
            <el-icon><Hide v-if="!allCheckedHidden" /><View v-else /></el-icon>
            <span>{{ allCheckedHidden ? '取消隐藏' : '隐藏' }}</span>
          </button>

          <!-- Lock / Unlock -->
          <button class="pp-bar-btn" :title="allCheckedLocked ? '解锁' : '锁定'" @click="batchLock">
            <el-icon><Unlock v-if="allCheckedLocked" /><Lock v-else /></el-icon>
            <span>{{ allCheckedLocked ? '解锁' : '锁定' }}</span>
          </button>

          <!-- Merge (only when 2+) -->
          <button
            v-if="checkedIds.size >= 2"
            class="pp-bar-btn"
            title="合并"
            @click="showMergeDialog = true"
          >
            <el-icon><Connection /></el-icon>
            <span>合并</span>
          </button>

          <!-- Delete -->
          <button class="pp-bar-btn pp-bar-btn--danger" title="删除" @click="batchDelete">
            <el-icon><Delete /></el-icon>
            <span>删除</span>
          </button>
        </div>
      </div>
    </Transition>

    <!-- ── Merge dialog ───────────────────────────────────────────────────── -->
    <el-dialog
      v-model="showMergeDialog"
      title="合并人物"
      width="400px"
      destroy-on-close
    >
      <p class="pp-merge-hint">选择要保留的人物，其余人脸数据将合并入该人物：</p>
      <div class="pp-merge-list">
        <div
          v-for="person in checkedPersons"
          :key="person.id"
          class="pp-merge-item"
          :class="{ 'is-target': mergeTargetId === person.id }"
          @click="mergeTargetId = person.id"
        >
          <div class="pp-merge-avatar">
            <img
              v-if="person.cover_path"
              :src="personsApi.cropUrl(person.cover_path)"
              class="pp-merge-img"
              @error="onImgErr"
            />
            <el-icon v-else><User /></el-icon>
          </div>
          <span class="pp-merge-name">{{ person.name }}</span>
          <span class="pp-merge-count">{{ person.photo_count }} 张</span>
          <el-icon v-if="mergeTargetId === person.id" class="pp-merge-check" color="#10b981"><Select /></el-icon>
        </div>
      </div>
      <template #footer>
        <el-button @click="showMergeDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!mergeTargetId" @click="doMerge">
          合并
        </el-button>
      </template>
    </el-dialog>

    <!-- ── Image viewer ───────────────────────────────────────────────────── -->
    <ImageViewer
      :visible="!!viewerPhoto"
      :photo="viewerPhoto"
      :has-prev="viewerIndex > 0"
      :has-next="viewerIndex < personStore.activePhotos.length - 1"
      @close="viewerPhoto = null"
      @navigate="navigateViewer"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  CircleCheck, Close, Connection, Delete, Hide, Lock, Loading,
  PictureFilled, Refresh, Select, Unlock, User, VideoPlay, View,
} from '@element-plus/icons-vue'
import { usePersonStore } from '@/stores/usePersonStore'
import { personsApi } from '@/api/persons'
import ImageViewer from '@/components/gallery/ImageViewer.vue'
import type { Person } from '@/types/person'
import type { Photo } from '@/types/photo'

const personStore = usePersonStore()

// ── UI state ───────────────────────────────────────────────────────────────
const showHidden   = ref(false)
const banner       = ref('')
const stripRef     = ref<HTMLElement | null>(null)

// ── Active person (photos shown below) ────────────────────────────────────
const activePerson = computed(() => personStore.activePerson)

// ── Multi-select ──────────────────────────────────────────────────────────
const checkedIds   = ref<Set<number>>(new Set())
const checkedPersons = computed(() =>
  personStore.persons.filter((p) => checkedIds.value.has(p.id))
)
const allCheckedHidden = computed(() =>
  checkedPersons.value.length > 0 && checkedPersons.value.every((p) => p.is_hidden)
)
const allCheckedLocked = computed(() =>
  checkedPersons.value.length > 0 && checkedPersons.value.every((p) => p.is_locked)
)

function clearChecked() {
  checkedIds.value = new Set()
}

function toggleCheck(id: number) {
  const s = new Set(checkedIds.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  checkedIds.value = s
}

// ── Visible persons ────────────────────────────────────────────────────────
const visiblePersons = computed(() =>
  personStore.persons.filter((p) => showHidden.value || !p.is_hidden)
)

// Refetch when showHidden toggles
watch(showHidden, (val) => personStore.fetchPersons(val))

// Load next page (appends to strip)
function loadMore() {
  personStore.loadMorePersons(showHidden.value)
}

// ── Inline rename ──────────────────────────────────────────────────────────
const editingId    = ref<number | null>(null)
const editingName  = ref('')
const nameInputRef = ref<HTMLInputElement | null>(null)

function startEdit(person: Person) {
  editingId.value   = person.id
  editingName.value = person.name
  nextTick(() => nameInputRef.value?.focus())
}

function cancelEdit() {
  editingId.value = null
}

async function commitRename(person: Person) {
  const name = editingName.value.trim()
  editingId.value = null
  if (!name || name === person.name) return
  try {
    await personStore.renamePerson(person.id, name)
    showBanner(`已重命名为「${name}」`)
  } catch {
    ElMessage.error('重命名失败')
  }
}

// ── Circle click interaction ───────────────────────────────────────────────
function onCircleClick(person: Person) {
  // In select mode: clicking circle also toggles check
  if (checkedIds.value.size > 0) {
    toggleCheck(person.id)
    return
  }
  // Normal: activate person → show their photos
  personStore.selectPerson(person)
}

// ── Photo viewer ───────────────────────────────────────────────────────────
const viewerPhoto  = ref<Photo | null>(null)
const viewerIndex  = ref(0)

function openViewer(photo: Photo) {
  viewerIndex.value = personStore.activePhotos.findIndex((p) => p.id === photo.id)
  viewerPhoto.value = photo
}

function navigateViewer(delta: 1 | -1) {
  const photos = personStore.activePhotos
  viewerIndex.value = Math.max(0, Math.min(photos.length - 1, viewerIndex.value + delta))
  viewerPhoto.value = photos[viewerIndex.value]
}

// ── Date range label ───────────────────────────────────────────────────────
const dateRange = computed(() => {
  const photos = personStore.activePhotos
  if (!photos.length) return ''
  const dates = photos
    .map((p) => p.taken_at)
    .filter(Boolean)
    .map((d) => new Date(d as string))
    .sort((a, b) => +a - +b)
  if (!dates.length) return ''
  const fmt = (d: Date) =>
    `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
  if (dates.length === 1 || fmt(dates[0]) === fmt(dates[dates.length - 1]))
    return fmt(dates[0])
  return `${fmt(dates[0])} 至 ${fmt(dates[dates.length - 1])}`
})

// ── Batch actions ──────────────────────────────────────────────────────────
async function batchHide() {
  const targetHidden = !allCheckedHidden.value
  await Promise.all(
    [...checkedIds.value].map((id) => personStore.hidePerson(id, targetHidden))
  )
  showBanner(targetHidden ? `已隐藏 ${checkedIds.value.size} 位人物` : `已取消隐藏`)
  clearChecked()
}

async function batchLock() {
  const targetLocked = !allCheckedLocked.value
  await Promise.all(
    [...checkedIds.value].map((id) => personStore.lockPerson(id, targetLocked))
  )
  showBanner(targetLocked ? `已锁定 ${checkedIds.value.size} 位人物` : `已解锁`)
  clearChecked()
}

async function batchDelete() {
  const locked = checkedPersons.value.filter((p) => p.is_locked)
  if (locked.length) {
    ElMessage.warning(`有 ${locked.length} 位锁定人物无法删除`)
    return
  }
  try {
    await ElMessageBox.confirm(
      `将删除 ${checkedIds.value.size} 位人物的人脸数据，照片本身不受影响。`,
      '删除人物',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch { return }

  const ids = [...checkedIds.value]
  clearChecked()
  let failed = 0
  await Promise.all(
    ids.map(async (id) => {
      try { await personStore.deletePerson(id) }
      catch { failed++ }
    })
  )
  showBanner(failed ? `删除完成，${failed} 个失败` : `已删除 ${ids.length} 位人物`)
}

// ── Merge dialog ───────────────────────────────────────────────────────────
const showMergeDialog = ref(false)
const mergeTargetId   = ref<number | null>(null)

watch(showMergeDialog, (open) => {
  if (open) mergeTargetId.value = checkedPersons.value[0]?.id ?? null
})

async function doMerge() {
  if (!mergeTargetId.value) return
  const targetId  = mergeTargetId.value
  const sourceIds = [...checkedIds.value].filter((id) => id !== targetId)
  showMergeDialog.value = false
  clearChecked()

  for (const sid of sourceIds) {
    await personStore.mergePersons(sid, targetId)
  }
  showBanner('合并完成')
}

// ── Run analysis ───────────────────────────────────────────────────────────
async function runAnalysis() {
  try {
    const result = await personStore.runAnalysis()
    showBanner(result.message)
  } catch {
    ElMessage.error('识别失败，请重试')
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────
function showBanner(msg: string) {
  banner.value = msg
  setTimeout(() => { banner.value = '' }, 4000)
}

function onImgErr(e: Event) {
  (e.target as HTMLImageElement).style.display = 'none'
}

// ── Lifecycle ──────────────────────────────────────────────────────────────
onMounted(() => personStore.fetchPersons(false))
</script>

<style scoped lang="scss">
.pp-root {
  min-height: 100%;
  color: var(--no-text-primary);
  font-family: var(--no-font-sans);
  padding-bottom: 100px; // space for action bar
}

// ── Header ────────────────────────────────────────────────────────────────
.pp-header {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 12px; flex-wrap: wrap; margin-bottom: 20px;
}
.pp-title {
  font-size: 22px; font-weight: 600; letter-spacing: -0.02em; margin: 0 0 2px;
}
.pp-subtitle {
  font-size: 12px; color: var(--no-text-secondary); margin: 0;
}
.pp-header-actions {
  display: flex; align-items: center; gap: 10px;
}
.pp-running {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--no-text-secondary);
}

// ── Banner ────────────────────────────────────────────────────────────────
.pp-banner {
  display: flex; align-items: center; gap: 8px;
  background: var(--no-accent-subtle); border: 1px solid var(--no-accent-border);
  border-radius: var(--no-radius-btn); padding: 8px 14px;
  font-size: 13px; color: var(--no-accent); margin-bottom: 16px;
}
.pp-banner-close {
  margin-left: auto; background: none; border: none;
  color: var(--no-text-muted); cursor: pointer; font-size: 12px;
  &:hover { color: var(--no-text-primary); }
}
.pp-fade-enter-active, .pp-fade-leave-active { transition: all .2s ease; }
.pp-fade-enter-from, .pp-fade-leave-to { opacity: 0; transform: translateY(-6px); }

// ── Empty ─────────────────────────────────────────────────────────────────
.pp-empty {
  display: flex; flex-direction: column; align-items: center;
  padding: 80px 20px; gap: 10px; text-align: center;
}
.pp-empty-icon { font-size: 52px; }
.pp-empty-text { font-size: 17px; font-weight: 600; margin: 0; }
.pp-empty-sub  { font-size: 13px; color: var(--no-text-muted); margin: 0; }

// ── Face strip ────────────────────────────────────────────────────────────
.pp-face-strip {
  display: flex;
  flex-direction: row;
  gap: 14px;
  overflow-x: auto;
  padding: 10px 2px 16px;
  scrollbar-width: none;
  &::-webkit-scrollbar { display: none; }
}

.pp-skeleton-strip {
  .pp-skel-circle {
    flex-shrink: 0;
    width: 88px; height: 88px; border-radius: 50%;
    background: linear-gradient(90deg, var(--no-bg-card) 25%, var(--no-border-low) 50%, var(--no-bg-card) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.4s infinite;
  }
}

// ── Face item ─────────────────────────────────────────────────────────────
.pp-face-item {
  flex-shrink: 0;
  display: flex; flex-direction: column; align-items: center;
  gap: 6px; cursor: pointer; width: 88px;

  &.is-hidden { opacity: 0.45; }
}

// ── Circle ────────────────────────────────────────────────────────────────
.pp-circle {
  position: relative;
  width: 82px; height: 82px; border-radius: 50%;
  border: 3px solid var(--no-border-low);
  background: var(--no-bg-card);
  overflow: visible; // allow checkbox to overflow
  transition: border-color 0.15s, box-shadow 0.15s;

  .pp-face-item:hover &,
  .pp-face-item.is-active & {
    border-color: var(--no-accent);
    box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.25);
  }
  .pp-face-item.is-checked & {
    border-color: var(--no-accent);
    box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.35);
  }
}

.pp-avatar {
  width: 76px; height: 76px; border-radius: 50%;
  object-fit: cover; display: block;
  position: absolute; inset: 0; margin: auto;
  transition: transform 0.2s;
  .pp-face-item:hover & { transform: scale(1.05); }
}

.pp-avatar-ph {
  position: absolute; inset: 0; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: var(--no-text-muted); background: var(--no-border-low);
}

// ── Checkbox (top-right of circle) ────────────────────────────────────────
.pp-checkbox {
  position: absolute;
  top: -4px; right: -4px;
  width: 22px; height: 22px;
  border-radius: 50%;
  border: 2px solid var(--no-border-low);
  background: var(--no-bg-main);
  display: flex; align-items: center; justify-content: center;
  opacity: 0;
  transition: opacity 0.15s, background 0.15s, border-color 0.15s;
  z-index: 2;
  cursor: pointer;

  .pp-face-item:hover & { opacity: 1; }

  &.is-checked {
    opacity: 1 !important;
    background: var(--no-accent);
    border-color: var(--no-accent);
    color: #fff;
  }
}

// ── Lock badge ────────────────────────────────────────────────────────────
.pp-lock-badge {
  position: absolute;
  bottom: -2px; right: -2px;
  width: 18px; height: 18px; border-radius: 50%;
  background: rgba(245, 158, 11, 0.9);
  display: flex; align-items: center; justify-content: center;
  color: #fff; z-index: 2;
}

// ── Preview photos (4 mini thumbs below name) ─────────────────────────────
.pp-preview-strip {
  display: flex; gap: 2px; justify-content: center;
  width: 88px; flex-wrap: wrap;
}
.pp-preview-thumb {
  width: 20px; height: 20px; border-radius: 2px;
  object-fit: cover; display: block;
  flex-shrink: 0;
}

// ── Load more in strip ─────────────────────────────────────────────────────
.pp-load-more-item {
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  width: 60px;
}
.pp-load-more-btn {
  width: 52px; height: 52px; border-radius: 50%;
  border: 2px dashed var(--no-border-low);
  background: none; cursor: pointer;
  color: var(--no-text-muted); font-size: 11px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 2px; line-height: 1.2; text-align: center;
  transition: border-color 0.15s, color 0.15s;

  &:hover:not(:disabled) {
    border-color: var(--no-accent);
    color: var(--no-accent);
  }
  &:disabled { cursor: default; }
  .el-icon { font-size: 20px; }
}

// ── Name ──────────────────────────────────────────────────────────────────
.pp-face-name {
  width: 88px; text-align: center;
}
.pp-name-text {
  font-size: 12px; color: var(--no-text-secondary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  display: block; transition: color 0.15s; cursor: text;
  .pp-face-item:hover & { color: var(--no-text-primary); }
  .pp-face-item.is-active & { color: var(--no-accent); font-weight: 500; }
}
.pp-name-input {
  width: 100%; background: var(--no-border-low);
  border: 1px solid var(--no-accent); border-radius: 4px;
  color: var(--no-text-primary); font-size: 11px;
  padding: 2px 4px; outline: none; text-align: center;
}

// ── Photos section ────────────────────────────────────────────────────────
.pp-photos-section {
  margin-top: 8px;
}

.pp-photos-header {
  display: flex; align-items: baseline; justify-content: space-between;
  padding: 4px 0 12px; border-bottom: 1px solid var(--no-border-low);
  margin-bottom: 12px;
}
.pp-photos-meta { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.pp-photos-name {
  font-size: 15px; font-weight: 600; color: var(--no-text-primary);
}
.pp-photos-range { font-size: 13px; color: var(--no-text-secondary); }
.pp-photos-count { font-size: 13px; color: var(--no-text-muted); white-space: nowrap; }

.pp-photos-loading {
  display: flex; justify-content: center; padding: 40px;
  color: var(--no-text-muted);
}

.pp-photos-empty {
  display: flex; align-items: center; gap: 8px;
  padding: 40px; justify-content: center;
  font-size: 14px; color: var(--no-text-muted);
}

.pp-photos-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 4px;
}
.pp-photo-cell {
  aspect-ratio: 1/1; overflow: hidden;
  border-radius: 3px; cursor: pointer;
  &:hover img { transform: scale(1.05); }
}
.pp-photo-thumb {
  width: 100%; height: 100%; object-fit: cover;
  display: block; transition: transform 0.2s;
}

// ── Bottom action bar ─────────────────────────────────────────────────────
.pp-action-bar {
  position: fixed;
  bottom: 28px; left: 50%; transform: translateX(-50%);
  z-index: 900;
  display: flex; align-items: center; gap: 12px;
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  border-radius: var(--no-radius-pill);
  padding: 10px 20px;
  box-shadow: 0 8px 32px rgba(0,0,0,.5);
  white-space: nowrap;
}

.pp-bar-cancel {
  background: none; border: none; cursor: pointer;
  color: var(--no-text-muted); display: flex; align-items: center;
  &:hover { color: var(--no-text-primary); }
}
.pp-bar-count {
  font-size: 13px; color: var(--no-text-secondary);
  padding-right: 4px;
  border-right: 1px solid var(--no-border-low);
}
.pp-bar-actions {
  display: flex; align-items: center; gap: 4px;
}
.pp-bar-btn {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  background: none; border: none; cursor: pointer;
  color: var(--no-text-secondary); font-size: 10px;
  padding: 6px 10px; border-radius: var(--no-radius-btn);
  transition: background 0.15s, color 0.15s;

  .el-icon { font-size: 18px; }

  &:hover {
    background: var(--no-border-low);
    color: var(--no-text-primary);
  }
  &--danger:hover {
    background: rgba(239, 68, 68, 0.12);
    color: #f87171;
  }
}

.pp-bar-enter-active, .pp-bar-leave-active { transition: all .2s ease; }
.pp-bar-enter-from, .pp-bar-leave-to { transform: translate(-50%, 20px); opacity: 0; }

// ── Merge dialog ──────────────────────────────────────────────────────────
.pp-merge-hint { font-size: 13px; color: var(--no-text-secondary); margin: 0 0 12px; }
.pp-merge-list { display: flex; flex-direction: column; gap: 6px; }
.pp-merge-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: var(--no-radius-btn);
  border: 1.5px solid var(--no-border-low); cursor: pointer;
  transition: border-color 0.15s;
  &.is-target { border-color: var(--no-accent); background: var(--no-accent-subtle); }
  &:hover:not(.is-target) { border-color: var(--no-text-muted); }
}
.pp-merge-avatar {
  width: 40px; height: 40px; border-radius: 50%;
  overflow: hidden; background: var(--no-border-low);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.pp-merge-img { width: 100%; height: 100%; object-fit: cover; }
.pp-merge-name { font-size: 14px; font-weight: 500; flex: 1; }
.pp-merge-count { font-size: 12px; color: var(--no-text-muted); }
.pp-merge-check { margin-left: 4px; }

// ── Spinner / shimmer ─────────────────────────────────────────────────────
.pp-spinner {
  display: inline-block; width: 12px; height: 12px;
  border: 2px solid var(--no-border-low); border-top-color: var(--no-text-secondary);
  border-radius: 50%; animation: spin 0.8s linear infinite;
}

@keyframes spin    { to { transform: rotate(360deg) } }
@keyframes shimmer { to { background-position: -200% 0 } }
</style>
