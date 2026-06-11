<template>
  <div class="pd-root">
    <!-- ── Back nav ─────────────────────────────────────────────── -->
    <div class="pd-topbar">
      <button class="pd-back" @click="router.back()">
        <el-icon><ArrowLeft /></el-icon>
        人物
      </button>
    </div>

    <!-- ── Loading ──────────────────────────────────────────────── -->
    <div v-if="loadingPerson" class="pd-loading">
      <span class="pd-spinner" />
    </div>

    <template v-else-if="person">
      <!-- ── Person hero ─────────────────────────────────────────── -->
      <div class="pd-hero">
        <div class="pd-avatar-wrap">
          <img
            v-if="person.cover_path"
            :src="personsApi.cropUrl(person.cover_path)"
            class="pd-avatar"
            @error="onAvatarErr"
          />
          <div v-else class="pd-avatar-placeholder">
            {{ person.name.charAt(0) }}
          </div>
        </div>

        <div class="pd-hero-info">
          <!-- Inline name editing -->
          <div v-if="!editingName" class="pd-name-row" @click="startEdit">
            <h1 class="pd-name">{{ person.name }}</h1>
            <el-icon class="pd-edit-icon"><Edit /></el-icon>
          </div>
          <div v-else class="pd-name-edit">
            <input
              ref="nameInput"
              v-model="editingNameVal"
              class="pd-name-input"
              maxlength="50"
              @keydown.enter="commitRename"
              @keydown.escape="cancelEdit"
              @blur="commitRename"
            />
          </div>

          <p class="pd-meta">{{ person.photo_count }} 张照片</p>

          <div class="pd-hero-actions">
            <el-button size="small" @click="toggleHide">
              {{ person.is_hidden ? '取消隐藏' : '隐藏此人物' }}
            </el-button>
          </div>
        </div>
      </div>

      <!-- ── Photo timeline grid ────────────────────────────────── -->
      <div class="pd-content">
        <div v-if="loadingPhotos && photos.length === 0" class="pd-loading-photos">
          <span class="pd-spinner" />
          加载照片…
        </div>

        <div v-else-if="photos.length === 0" class="pd-no-photos">
          <el-empty description="暂无照片" />
        </div>

        <template v-else>
          <div
            v-for="year in sortedYears"
            :key="year"
            class="pd-year-group"
          >
            <div class="pd-year-label">{{ year }}</div>

            <div v-for="month in sortedMonths(year)" :key="month">
              <div v-for="day in sortedDays(year, month)" :key="day">
                <div class="pd-day-header">
                  <span class="pd-day-title">{{ parseInt(month) }}月{{ parseInt(day) }}日</span>
                  <span class="pd-day-count">{{ grouped[year][month][day].length }} 张</span>
                </div>

                <div class="pd-photo-grid">
                  <div
                    v-for="photo in grouped[year][month][day]"
                    :key="photo.id"
                    class="pd-photo-cell"
                    @click="openViewer(photo)"
                  >
                    <img
                      :src="`/api/v1/thumbnails/${photo.id}?size=256`"
                      :alt="photo.file_name"
                      loading="lazy"
                      class="pd-thumb"
                      @error="onThumbErr"
                    />
                    <div class="pd-overlay">
                      <span class="pd-overlay-name">{{ photo.file_name }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Infinite scroll sentinel -->
          <div ref="sentinel" style="height:1px" />
          <div v-if="loadingPhotos" class="pd-load-more">
            <span class="pd-spinner pd-spinner--sm" />加载更多…
          </div>
        </template>
      </div>
    </template>

    <div v-else class="pd-loading">
      <el-empty description="未找到此人物" />
    </div>

    <!-- ── ImageViewer ───────────────────────────────────────────── -->
    <ImageViewer
      :visible="!!viewerPhoto"
      :photo="viewerPhoto"
      :has-prev="viewerIndex > 0"
      :has-next="viewerIndex < photos.length - 1"
      @close="closeViewer"
      @navigate="onNavigate"
      @soft-delete="onSoftDelete"
      @toast="showToast"
    />

    <!-- ── Toast ────────────────────────────────────────────────── -->
    <Transition name="pd-toast">
      <div v-if="toast" class="pd-toast">
        <span class="pd-toast-dot" />{{ toast }}
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePersonStore } from '@/stores/usePersonStore'
import { personsApi } from '@/api/persons'
import ImageViewer from '@/components/gallery/ImageViewer.vue'
import type { Person } from '@/types/person'
import type { Photo } from '@/types/photo'

const route  = useRoute()
const router = useRouter()
const personStore = usePersonStore()

const personId = computed(() => Number(route.params.id))

// ── Person data ───────────────────────────────────────────────────────────────
const person = ref<Person | null>(null)
const loadingPerson = ref(true)

// ── Photo data ────────────────────────────────────────────────────────────────
const photos = ref<Photo[]>([])
const total = ref(0)
const page = ref(1)
const PAGE_SIZE = 80
const loadingPhotos = ref(false)

// ── Name editing ──────────────────────────────────────────────────────────────
const editingName = ref(false)
const editingNameVal = ref('')
const nameInput = ref<HTMLInputElement | null>(null)

// ── Viewer ────────────────────────────────────────────────────────────────────
const viewerPhoto = ref<Photo | null>(null)
const viewerIndex = ref(-1)

// ── Toast ─────────────────────────────────────────────────────────────────────
const toast = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null

// ── Infinite scroll ───────────────────────────────────────────────────────────
const sentinel = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

// ── Timeline grouping ─────────────────────────────────────────────────────────
const grouped = computed<Record<string, Record<string, Record<string, Photo[]>>>>(() => {
  const g: Record<string, Record<string, Record<string, Photo[]>>> = {}
  for (const p of photos.value) {
    const raw = p.exif?.taken_at ?? p.created_at
    const d   = raw ? new Date(raw) : null
    if (!d || isNaN(d.getTime())) continue
    const y = String(d.getFullYear())
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    if (!g[y])      g[y] = {}
    if (!g[y][m])   g[y][m] = {}
    if (!g[y][m][dd]) g[y][m][dd] = []
    g[y][m][dd].push(p)
  }
  return g
})

const sortedYears  = computed(() => Object.keys(grouped.value).sort((a, b) => +b - +a))
const sortedMonths = (y: string) => Object.keys(grouped.value[y] ?? {}).sort((a, b) => +b - +a)
const sortedDays   = (y: string, m: string) => Object.keys(grouped.value[y]?.[m] ?? {}).sort((a, b) => +b - +a)

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  await loadPerson()
  await loadPhotos(true)

  observer = new IntersectionObserver(
    (entries) => { if (entries[0].isIntersecting) loadNextPage() },
    { threshold: 0.1 },
  )
  if (sentinel.value) observer.observe(sentinel.value)
})

onUnmounted(() => {
  observer?.disconnect()
  if (toastTimer) clearTimeout(toastTimer)
})

// ── Data loaders ──────────────────────────────────────────────────────────────
async function loadPerson() {
  loadingPerson.value = true
  try {
    const { data } = await personsApi.get(personId.value)
    person.value = data
  } catch {
    person.value = null
  } finally {
    loadingPerson.value = false
  }
}

async function loadPhotos(reset = false) {
  if (reset) {
    page.value = 1
    photos.value = []
    total.value  = 0
  }
  loadingPhotos.value = true
  try {
    const { data } = await personsApi.photos(personId.value, page.value, PAGE_SIZE)
    if (reset) {
      photos.value = data.items
    } else {
      photos.value.push(...data.items)
    }
    total.value = data.total
  } finally {
    loadingPhotos.value = false
  }
}

function loadNextPage() {
  if (loadingPhotos.value || photos.value.length >= total.value) return
  page.value++
  loadPhotos(false)
}

// ── Name editing ──────────────────────────────────────────────────────────────
function startEdit() {
  if (!person.value) return
  editingNameVal.value = person.value.name
  editingName.value = true
  nextTick(() => nameInput.value?.focus())
}

function cancelEdit() {
  editingName.value = false
}

async function commitRename() {
  const name = editingNameVal.value.trim()
  editingName.value = false
  if (!name || !person.value || name === person.value.name) return
  await personStore.renamePerson(person.value.id, name)
  person.value = { ...person.value, name }
  showToast(`已重命名为「${name}」`)
}

// ── Hide ──────────────────────────────────────────────────────────────────────
async function toggleHide() {
  if (!person.value) return
  await personStore.hidePerson(person.value.id, !person.value.is_hidden)
  person.value = { ...person.value, is_hidden: !person.value.is_hidden }
  showToast(person.value.is_hidden ? '已隐藏' : '已取消隐藏')
}

// ── Viewer ────────────────────────────────────────────────────────────────────
function openViewer(photo: Photo) {
  viewerIndex.value = photos.value.findIndex((p) => p.id === photo.id)
  viewerPhoto.value = photo
}

function closeViewer() {
  viewerPhoto.value = null
  viewerIndex.value = -1
}

function onNavigate(delta: 1 | -1) {
  const next = viewerIndex.value + delta
  if (next >= 0 && next < photos.value.length) {
    viewerIndex.value = next
    viewerPhoto.value = photos.value[next]
  }
}

function onSoftDelete(photoId: number) {
  photos.value = photos.value.filter((p) => p.id !== photoId)
  total.value -= 1
  if (photos.value.length === 0) closeViewer()
  else {
    const idx = Math.min(viewerIndex.value, photos.value.length - 1)
    viewerIndex.value = idx
    viewerPhoto.value = photos.value[idx]
  }
}

function showToast(msg: string) {
  toast.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 3000)
}

function onAvatarErr(e: Event) {
  (e.target as HTMLImageElement).style.display = 'none'
}

function onThumbErr(e: Event) {
  (e.target as HTMLImageElement).style.opacity = '0.15'
}
</script>

<style scoped lang="scss">
.pd-root {
  min-height: 100%;
  background: var(--no-bg-main);
  color: var(--no-text-primary);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  position: relative;
}

/* ── Topbar ──────────────────────────────────────────────────────── */
.pd-topbar {
  padding: 16px 24px 0;
}
.pd-back {
  background: none; border: none;
  color: var(--no-text-secondary); cursor: pointer;
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; padding: 0;
  transition: color 0.15s;
  &:hover { color: var(--no-text-primary); }
}

/* ── Hero ────────────────────────────────────────────────────────── */
.pd-hero {
  display: flex; align-items: flex-end;
  gap: 24px; padding: 24px 24px 28px;
  border-bottom: 1px solid var(--no-border-low);
}

.pd-avatar-wrap {
  width: 96px; height: 96px; flex-shrink: 0;
  border-radius: 50%; overflow: hidden;
  border: 2px solid var(--no-border-low);
  background: var(--no-bg-card);
}
.pd-avatar {
  width: 100%; height: 100%; object-fit: cover;
}
.pd-avatar-placeholder {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  font-size: 40px; font-weight: 700; color: #3f3f46;
}

.pd-hero-info { flex: 1; }

.pd-name-row {
  display: flex; align-items: center; gap: 8px; cursor: text;
  &:hover .pd-edit-icon { opacity: 1; }
}
.pd-name {
  font-size: 26px; font-weight: 900;
  letter-spacing: -0.03em; margin: 0;
}
.pd-edit-icon { opacity: 0; transition: opacity 0.15s; color: var(--no-text-muted); }

.pd-name-edit { display: flex; }
.pd-name-input {
  background: var(--no-border-low); border: 1px solid var(--no-accent);
  border-radius: 6px; color: var(--no-text-primary);
  font-size: 22px; font-weight: 800;
  padding: 4px 10px; outline: none; width: 300px;
}

.pd-meta { font-size: 13px; color: var(--no-text-muted); margin: 4px 0 12px; font-family: monospace; }
.pd-hero-actions { display: flex; gap: 8px; }

/* ── Content ─────────────────────────────────────────────────────── */
.pd-content { padding: 20px 24px 80px; }

.pd-loading, .pd-loading-photos {
  display: flex; align-items: center; justify-content: center;
  gap: 10px; padding: 60px; color: var(--no-text-muted); font-size: 13px;
}
.pd-no-photos { padding: 60px; }

/* ── Year / day ──────────────────────────────────────────────────── */
.pd-year-group { margin-bottom: 32px; }
.pd-year-label {
  font-size: 32px; font-weight: 900;
  color: #3f3f46; letter-spacing: -0.04em; margin-bottom: 12px;
}

.pd-day-header {
  position: sticky; top: 0; z-index: 10;
  background: rgba(11,11,12,.9);
  backdrop-filter: blur(8px);
  padding: 6px 0; margin-bottom: 8px;
  display: flex; align-items: baseline; gap: 8px;
  border-bottom: 1px solid rgba(39,39,42,.4);
}
.pd-day-title { font-size: 14px; font-weight: 600; }
.pd-day-count  { font-size: 11px; color: var(--no-text-muted); font-family: monospace; }

/* ── Photo grid ──────────────────────────────────────────────────── */
.pd-photo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 5px; margin-bottom: 16px;
}
.pd-photo-cell {
  aspect-ratio: 1; border-radius: var(--no-radius-btn); overflow: hidden;
  background: var(--no-bg-card); border: 1px solid var(--no-border-low);
  cursor: pointer; position: relative;
  transition: border-color 0.15s;
  &:hover { border-color: #3f3f46; }
}
.pd-thumb {
  width: 100%; height: 100%; object-fit: cover;
  transition: transform 0.3s;
  .pd-photo-cell:hover & { transform: scale(1.05); }
}
.pd-overlay {
  position: absolute; inset: 0;
  background: linear-gradient(to top, rgba(0,0,0,.8), transparent);
  opacity: 0; transition: opacity 0.2s;
  display: flex; align-items: flex-end; padding: 7px;
  .pd-photo-cell:hover & { opacity: 1; }
}
.pd-overlay-name {
  font-size: 9px; color: var(--no-text-primary);
  font-family: monospace;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* ── Load more ───────────────────────────────────────────────────── */
.pd-load-more {
  text-align: center; padding: 20px;
  color: var(--no-text-muted); font-size: 12px;
  font-family: monospace;
  display: flex; align-items: center;
  justify-content: center; gap: 8px;
}

/* ── Toast ───────────────────────────────────────────────────────── */
.pd-toast {
  position: fixed; bottom: 28px; left: 50%;
  transform: translateX(-50%); z-index: 1999;
  background: var(--no-bg-card);
  border: 1px solid rgba(74,222,128,.4);
  color: var(--no-text-primary); padding: 9px 20px;
  border-radius: var(--no-radius-pill); font-size: 12px;
  display: flex; align-items: center; gap: 8px;
  box-shadow: 0 8px 32px rgba(0,0,0,.5);
  white-space: nowrap;
}
.pd-toast-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--no-accent); animation: pulse 1.5s infinite;
}
.pd-toast-enter-active, .pd-toast-leave-active { transition: all .2s ease }
.pd-toast-enter-from, .pd-toast-leave-to { transform: translate(-50%,14px); opacity:0 }

/* ── Spinner ─────────────────────────────────────────────────────── */
.pd-spinner {
  display: inline-block; width: 16px; height: 16px;
  border: 2px solid var(--no-border-low); border-top-color: var(--no-text-secondary);
  border-radius: 50%; animation: spin 0.8s linear infinite;
  &--sm { width: 12px; height: 12px; }
}

@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
@keyframes spin   { to{transform:rotate(360deg)} }
</style>
