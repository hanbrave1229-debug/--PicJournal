<template>
  <div class="pp-root">
    <!-- ── Toast ──────────────────────────────────────────────────────── -->
    <Transition name="pp-toast">
      <div v-if="toast" class="pp-toast">
        <span class="pp-toast-dot" />{{ toast }}
      </div>
    </Transition>

    <!-- ── Header ─────────────────────────────────────────────────────── -->
    <div class="pp-header">
      <div class="pp-header-left">
        <div>
          <h1 class="pp-title">人物识别</h1>
          <p class="pp-subtitle">基于本地 DBSCAN 算法安全聚类，您的面部特征数据不会上传云端。</p>
        </div>
      </div>
      <div class="pp-header-right">
        <el-button size="small" :loading="personStore.loading" @click="personStore.fetchPersons(true)">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button
          v-if="!personStore.running"
          type="primary"
          size="small"
          :loading="personStore.loading"
          @click="runAnalysis"
        >
          <el-icon><VideoPlay /></el-icon>
          识别人脸
        </el-button>
        <div v-else class="pp-running">
          <span class="pp-spinner" />
          分析中…
        </div>
        <el-checkbox v-model="showHidden" label="显示已隐藏" size="small" />
      </div>
    </div>

    <!-- ── Run result banner ────────────────────────────────────────── -->
    <Transition name="pp-banner">
      <div v-if="lastResult" class="pp-banner">
        <el-icon><CircleCheck /></el-icon>
        {{ lastResult.message }}
        <button class="pp-banner-close" @click="lastResult = null">✕</button>
      </div>
    </Transition>

    <!-- ── Loading skeleton ─────────────────────────────────────────── -->
    <div v-if="personStore.loading && visiblePersons.length === 0" class="pp-skeletons">
      <div v-for="i in 12" :key="i" class="pp-skeleton-item" />
    </div>

    <!-- ── Empty state ──────────────────────────────────────────────── -->
    <div v-else-if="!personStore.loading && visiblePersons.length === 0" class="pp-empty">
      <div class="pp-empty-icon">👤</div>
      <div class="pp-empty-text">尚未识别到人物</div>
      <div class="pp-empty-sub">点击「识别人脸」开始分析照片库中的人脸</div>
      <el-button type="primary" @click="runAnalysis" :loading="personStore.running">
        开始识别
      </el-button>
    </div>

    <!-- ── Person grid ───────────────────────────────────────────────── -->
    <div v-else class="pp-grid">
      <div
        v-for="person in visiblePersons"
        :key="person.id"
        class="pp-person"
        :class="{ 'pp-person--hidden': person.is_hidden }"
        @click="goToDetail(person)"
      >
        <!-- Circular avatar -->
        <div class="pp-avatar-wrap">
          <img
            v-if="person.cover_path"
            :src="personsApi.cropUrl(person.cover_path)"
            :alt="person.name"
            class="pp-avatar"
            @error="onAvatarErr"
          />
          <div v-else class="pp-avatar-placeholder">
            <el-icon size="36"><User /></el-icon>
          </div>
          <!-- Hidden badge -->
          <span v-if="person.is_hidden" class="pp-badge-hidden">已隐藏</span>
          <!-- Action overlay (hide/show) -->
          <div class="pp-avatar-actions" @click.stop>
            <button
              class="pp-action-btn"
              :title="person.is_hidden ? '取消隐藏' : '隐藏'"
              @click="toggleHide(person)"
            >
              <el-icon><Hide v-if="!person.is_hidden" /><View v-else /></el-icon>
            </button>
          </div>
        </div>

        <!-- Name (click to edit inline) -->
        <div class="pp-person-info" @click.stop>
          <div v-if="editingId !== person.id" class="pp-name-row" @click="startEdit(person)">
            <span class="pp-name">{{ person.name }}</span>
            <el-icon class="pp-edit-icon"><Edit /></el-icon>
          </div>
          <div v-else class="pp-name-edit" @click.stop>
            <input
              ref="nameInput"
              v-model="editingName"
              class="pp-name-input"
              maxlength="50"
              @keydown.enter="commitRename(person)"
              @keydown.escape="cancelEdit"
              @blur="commitRename(person)"
            />
          </div>
          <span class="pp-photo-count">{{ person.photo_count }} 张照片</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { usePersonStore } from '@/stores/usePersonStore'
import { personsApi } from '@/api/persons'
import type { Person, FaceRunResponse } from '@/types/person'

const router = useRouter()
const personStore = usePersonStore()

// ── State ──────────────────────────────────────────────────────────────────
const showHidden = ref(false)
const lastResult = ref<FaceRunResponse | null>(null)
const toast = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null

// ── Inline name editing ────────────────────────────────────────────────────
const editingId = ref<number | null>(null)
const editingName = ref('')
const nameInput = ref<HTMLInputElement | null>(null)

const visiblePersons = computed(() =>
  personStore.persons.filter((p) => showHidden.value || !p.is_hidden),
)

// ── Lifecycle ──────────────────────────────────────────────────────────────
onMounted(() => personStore.fetchPersons(true))

// ── Actions ────────────────────────────────────────────────────────────────
async function runAnalysis() {
  try {
    const result = await personStore.runAnalysis()
    lastResult.value = result
    showToast(result.message)
  } catch {
    showToast('识别失败，请重试')
  }
}

function goToDetail(person: Person) {
  if (editingId.value === person.id) return
  router.push({ name: 'person-detail', params: { id: person.id } })
}

function startEdit(person: Person) {
  editingId.value = person.id
  editingName.value = person.name
  nextTick(() => nameInput.value?.focus())
}

function cancelEdit() {
  editingId.value = null
  editingName.value = ''
}

async function commitRename(person: Person) {
  const name = editingName.value.trim()
  editingId.value = null
  if (!name || name === person.name) return
  try {
    await personStore.renamePerson(person.id, name)
    showToast(`已重命名为「${name}」`)
  } catch {
    showToast('重命名失败')
  }
}

async function toggleHide(person: Person) {
  await personStore.hidePerson(person.id, !person.is_hidden)
  showToast(person.is_hidden ? `已显示「${person.name}」` : `已隐藏「${person.name}」`)
}

function onAvatarErr(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.display = 'none'
  const wrap = img.closest('.pp-avatar-wrap') as HTMLElement | null
  if (wrap) {
    const ph = wrap.querySelector('.pp-avatar-placeholder') as HTMLElement | null
    if (ph) (ph as HTMLElement).style.display = 'flex'
  }
}

function showToast(msg: string) {
  toast.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 3000)
}
</script>

<style scoped lang="scss">
/* ── Root ────────────────────────────────────────────────────────────── */
.pp-root {
  min-height: 100%;
  color: var(--no-text-primary);
  font-family: var(--no-font-sans);
  position: relative;
}

/* ── Toast ───────────────────────────────────────────────────────────── */
.pp-toast {
  position: fixed;
  bottom: 28px; left: 50%;
  transform: translateX(-50%);
  z-index: 1999;
  background: var(--no-bg-card);
  border: 1px solid var(--no-accent-border);
  color: var(--no-text-primary);
  padding: 9px 20px;
  border-radius: var(--no-radius-pill);
  font-size: 12px;
  display: flex; align-items: center; gap: 8px;
  box-shadow: 0 8px 32px rgba(0,0,0,.5);
  white-space: nowrap;
}
.pp-toast-dot {
  width: 7px; height: 7px;
  border-radius: 50%; background: var(--no-accent);
  animation: pulse 1.5s infinite;
}
.pp-toast-enter-active, .pp-toast-leave-active { transition: all .2s ease }
.pp-toast-enter-from, .pp-toast-leave-to { transform: translate(-50%, 14px); opacity: 0 }

/* ── Header ──────────────────────────────────────────────────────────── */
.pp-header {
  display: flex; align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 28px; gap: 12px; flex-wrap: wrap;
}
.pp-header-left { display: flex; align-items: baseline; gap: 12px; }
.pp-title {
  font-size: 24px; font-weight: 600;
  letter-spacing: -0.02em; margin: 0 0 4px;
}
.pp-subtitle {
  font-size: 13px; color: var(--no-text-secondary);
  margin: 0;
}
.pp-header-right { display: flex; align-items: center; gap: 12px; }

.pp-running {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--no-text-secondary); font-family: monospace;
}

/* ── Banner ──────────────────────────────────────────────────────────── */
.pp-banner {
  background: var(--no-accent-subtle);
  border: 1px solid var(--no-accent-border);
  border-radius: var(--no-radius-btn);
  padding: 10px 16px;
  font-size: 13px; color: var(--no-accent);
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 20px;
}
.pp-banner-close {
  margin-left: auto; background: none; border: none;
  color: var(--no-text-muted); cursor: pointer; font-size: 12px;
  &:hover { color: var(--no-text-primary); }
}
.pp-banner-enter-active, .pp-banner-leave-active { transition: all .2s ease }
.pp-banner-enter-from, .pp-banner-leave-to { opacity: 0; transform: translateY(-8px); }

/* ── Skeletons ───────────────────────────────────────────────────────── */
.pp-skeletons {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 20px;
}
.pp-skeleton-item {
  height: 160px; border-radius: var(--no-radius-pill);
  background: linear-gradient(90deg, var(--no-bg-card) 25%, var(--no-border-low) 50%, var(--no-bg-card) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
}

/* ── Empty ───────────────────────────────────────────────────────────── */
.pp-empty {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 80px 20px; gap: 12px;
}
.pp-empty-icon { font-size: 56px; }
.pp-empty-text { font-size: 18px; font-weight: 600; color: var(--no-text-primary); }
.pp-empty-sub { font-size: 13px; color: var(--no-text-muted); }

/* ── Person grid ─────────────────────────────────────────────────────── */
.pp-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 24px;
}

/* ── Person item (floating circles) ─────────────────────────────────── */
.pp-person {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  cursor: pointer;

  &--hidden { opacity: 0.45; }
}

/* ── Circular avatar ─────────────────────────────────────────────────── */
.pp-avatar-wrap {
  position: relative;
  width: 120px; height: 120px;
  border-radius: 50%;
  border: 3px solid var(--no-border-low);
  background: var(--no-bg-card);
  overflow: hidden;
  flex-shrink: 0;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);

  .pp-person:hover & {
    border-color: var(--no-accent);
    box-shadow: 0 10px 25px rgba(52, 211, 153, 0.2);
  }
}

.pp-avatar {
  width: 100%; height: 100%;
  object-fit: cover;
  transition: transform 0.3s;
  .pp-person:hover & { transform: scale(1.08); }
}

.pp-avatar-placeholder {
  display: flex; align-items: center; justify-content: center;
  width: 100%; height: 100%;
  background: var(--no-border-low);
  color: var(--no-text-muted);
  .pp-person:hover & { color: var(--no-accent); }
}

.pp-badge-hidden {
  position: absolute; top: 8px; right: 8px;
  background: rgba(0,0,0,.7); color: var(--no-text-secondary);
  font-size: 9px; padding: 2px 6px;
  border-radius: 6px; font-family: monospace;
}

.pp-avatar-actions {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0.4);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s;

  .pp-avatar-wrap:hover & { opacity: 1; }
}

.pp-action-btn {
  width: 30px; height: 30px;
  background: rgba(14, 15, 17, 0.8);
  backdrop-filter: blur(6px);
  border: 1px solid rgba(255,255,255,.15);
  border-radius: 50%;
  color: var(--no-text-secondary);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: color 0.15s, border-color 0.15s;

  &:hover { color: var(--no-text-primary); border-color: rgba(255,255,255,.3); }
}

/* ── Person info ─────────────────────────────────────────────────────── */
.pp-person-info {
  text-align: center;
  width: 100%;
}

.pp-name-row {
  display: inline-flex; align-items: center; gap: 4px;
  cursor: text;
  max-width: 100%;
}
.pp-name {
  font-size: 14px; font-weight: 500;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: var(--no-text-primary);
  transition: color 0.15s;
  .pp-person:hover & { color: var(--no-accent); }
}
.pp-edit-icon {
  opacity: 0; transition: opacity 0.15s;
  color: var(--no-text-muted); font-size: 11px; flex-shrink: 0;
  .pp-person:hover & { opacity: 0.6; }
}
.pp-name-edit { width: 100%; }
.pp-name-input {
  width: 100%; background: var(--no-border-low);
  border: 1px solid var(--no-accent); border-radius: 6px;
  color: var(--no-text-primary); font-size: 13px;
  padding: 3px 7px; outline: none; text-align: center;
}
.pp-photo-count {
  font-size: 12px; color: var(--no-text-secondary);
  font-family: var(--no-font-mono); display: block;
  margin-top: 4px;
}

/* ── Spinner ─────────────────────────────────────────────────────────── */
.pp-spinner {
  display: inline-block;
  width: 12px; height: 12px;
  border: 2px solid var(--no-border-low); border-top-color: var(--no-text-secondary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* ── Keyframes ───────────────────────────────────────────────────────── */
@keyframes pulse  { 0%,100%{opacity:1} 50%{opacity:.3} }
@keyframes spin   { to{transform:rotate(360deg)} }
@keyframes shimmer { to{background-position:-200% 0} }
</style>
