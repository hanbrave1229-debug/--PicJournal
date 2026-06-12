<template>
  <div class="diary-page">
    <!-- ── Header ──────────────────────────────────────────────────────────── -->
    <div class="diary-header">
      <div>
        <h1 class="diary-title">时光日志簿</h1>
        <p class="diary-subtitle">用照片刻录岁月，AI 替你执笔生活。</p>
      </div>
      <div class="diary-nav">
        <span class="diary-month-label">{{ currentYear }} 年 {{ currentMonth }} 月</span>
        <el-button-group>
          <el-button size="small" plain @click="prevMonth">
            <el-icon><ArrowLeft /></el-icon>
          </el-button>
          <el-button size="small" plain @click="goToday">今天</el-button>
          <el-button size="small" plain @click="nextMonth">
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </el-button-group>
      </div>
    </div>

    <!-- ── Calendar grid ───────────────────────────────────────────────────── -->
    <div class="calendar-weekdays">
      <div v-for="d in WEEKDAYS" :key="d">{{ d }}</div>
    </div>

    <div v-loading="loadingMonth" class="calendar-grid">
      <div
        v-for="cell in calendarCells"
        :key="cell.isPadding ? `pad-${cell.day}` : cell.day"
        class="calendar-cell"
        :class="{
          'is-padding': cell.isPadding,
          'is-today': isToday(cell.day),
          'has-diary': !!cell.diary,
        }"
        @click="!cell.isPadding && openDialog(cell.day, cell.diary)"
      >
        <!-- Padding cell -->
        <template v-if="cell.isPadding">
          <span class="cell-day-num cell-day-muted">{{ cell.day }}</span>
        </template>

        <!-- Empty day -->
        <template v-else-if="!cell.diary">
          <span class="cell-day-num" :class="{ 'cell-today-badge': isToday(cell.day) }">
            {{ cell.day }}
          </span>
          <div class="cell-empty-hint">
            <el-icon size="16" color="var(--no-text-disabled)"><EditPen /></el-icon>
          </div>
        </template>

        <!-- Day with diary -->
        <template v-else>
          <!-- Cover photo background -->
          <div
            class="cell-cover"
            :style="cell.diary.cover_thumbnail_url
              ? { backgroundImage: `url(${cell.diary.cover_thumbnail_url})` }
              : {}"
          />
          <!-- Gradient overlay -->
          <div class="cell-overlay" />
          <!-- Day number -->
          <span class="cell-day-num cell-day-over-photo" :class="{ 'cell-today-badge': isToday(cell.day) }">
            {{ cell.day }}
          </span>
          <!-- Mood emoji -->
          <div class="cell-mood-badge">{{ getMoodEmoji(cell.diary.mood) }}</div>
          <!-- Hover slide-up panel -->
          <div class="cell-hover-panel">
            <span class="cell-summary">{{ cell.diary.summary || '点击查看日记' }}</span>
          </div>
        </template>
      </div>
    </div>

    <!-- ── Write-diary Dialog ──────────────────────────────────────────────── -->
    <el-dialog
      v-model="dialogVisible"
      :title="`${currentYear} 年 ${currentMonth} 月 ${selectedDay} 日 · 手账记录`"
      width="960px"
      class="diary-dialog"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <div class="dialog-body">
        <!-- Left: photo panel -->
        <div class="dialog-photo-panel">
          <div class="panel-label">
            <span>今日快照 (已选 {{ selectedPhotoIds.length }})</span>
            <span class="panel-link" @click="togglePicker">
              {{ pickerOpen ? '收起' : '选择照片' }}
            </span>
          </div>

          <!-- Inline photo picker grid -->
          <Transition name="picker-slide">
            <div v-if="pickerOpen" v-loading="loadingPicker" class="picker-grid">
              <div
                v-for="photo in pickerPhotos"
                :key="photo.id"
                class="picker-thumb"
                :class="{ 'is-selected': selectedPhotoIds.includes(photo.id) }"
                @click="togglePickerPhoto(photo.id)"
              >
                <img :src="`/api/v1/thumbnails/${photo.id}/256`" alt="" loading="lazy" />
                <div v-if="selectedPhotoIds.includes(photo.id)" class="picker-check">
                  <el-icon size="9" color="#fff"><Check /></el-icon>
                </div>
              </div>
              <div v-if="!loadingPicker && pickerPhotos.length === 0" class="picker-empty">
                暂无照片
              </div>
            </div>
          </Transition>

          <!-- Photo strip (selected thumbnails) -->
          <div class="photo-strip">
            <div
              v-for="pid in selectedPhotoIds"
              :key="pid"
              class="photo-thumb selected"
              @click="deselectPhoto(pid)"
            >
              <img :src="`/api/v1/thumbnails/${pid}/256`" alt="" />
              <div class="thumb-check">
                <el-icon size="10" color="#fff"><Check /></el-icon>
              </div>
            </div>
            <div v-if="selectedPhotoIds.length === 0" class="photo-empty-hint">
              从图库选择照片后将显示在此处
            </div>
          </div>

          <!-- Cover photo big preview -->
          <div
            class="cover-preview"
            :style="selectedPhotoIds.length > 0
              ? { backgroundImage: `url(/api/v1/thumbnails/${selectedPhotoIds[0]}/256)` }
              : {}"
          >
            <div v-if="selectedPhotoIds.length === 0" class="cover-empty">
              <el-icon size="28" color="var(--no-text-disabled)"><Picture /></el-icon>
              <span>暂无封面照片</span>
            </div>
            <!-- Offline geo tag overlay -->
            <div v-if="coverPhotoGeo" class="cover-geo-tag">
              <span class="cover-geo-pin">📍</span>
              <span class="cover-geo-text">{{ coverPhotoGeo }}</span>
              <span class="cover-geo-badge">离线地理</span>
            </div>
          </div>
        </div>

        <!-- Right: write panel -->
        <div class="dialog-write-panel">
          <!-- Mood tracker -->
          <div class="mood-row">
            <span class="panel-label-sm">今日心情档案</span>
            <div class="mood-pills">
              <button
                v-for="m in MOODS"
                :key="m.name"
                class="mood-pill"
                :class="{ active: selectedMood === m.name }"
                :style="selectedMood === m.name ? { backgroundColor: m.color } : {}"
                @click="selectedMood = m.name"
                :title="m.label"
              >
                {{ m.emoji }}
              </button>
            </div>
          </div>

          <!-- Textarea -->
          <div class="write-area-wrap">
            <textarea
              v-model="diaryContent"
              class="write-textarea"
              :placeholder="'写下今天的感悟，或者让 AI 替你执笔...'"
            />
            <!-- AI generating overlay -->
            <Transition name="fade">
              <div v-if="isGenerating" class="generating-overlay">
                <div class="spinner" />
                <span class="generating-text">DeepSeek 正在回忆你的这一天...</span>
              </div>
            </Transition>
          </div>

          <!-- Action row -->
          <div class="dialog-actions">
            <el-button plain @click="dialogVisible = false">取消</el-button>
            <div class="action-right">
              <button class="ai-btn" :disabled="isGenerating" @click="triggerAI">
                <el-icon><MagicStick /></el-icon>
                AI 帮我写
              </button>
              <el-button
                type="primary"
                color="#34d399"
                class="save-btn"
                :loading="isSaving"
                @click="saveDiary"
              >
                保存日记
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- ── Polaroid Dialog ─────────────────────────────────────────────────── -->
    <el-dialog
      v-model="polaroidVisible"
      width="480px"
      class="diary-dialog polaroid-dialog"
      title="时光拍立得"
      destroy-on-close
    >
      <div class="polaroid-wrap">
        <div id="polaroid-canvas" class="polaroid-card">
          <!-- Photo -->
          <div
            class="polaroid-photo"
            :style="selectedPhotoIds.length > 0
              ? { backgroundImage: `url(/api/v1/thumbnails/${selectedPhotoIds[0]}/256)` }
              : {}"
          />
          <!-- Meta row -->
          <div class="polaroid-meta">
            <span class="polaroid-date">
              {{ currentYear }}.{{ String(currentMonth).padStart(2, '0') }}.{{ String(selectedDay).padStart(2, '0') }}
            </span>
            <span class="polaroid-location">📍 Local NAS Storage</span>
          </div>
          <!-- Content -->
          <p class="polaroid-content font-handwriting">{{ diaryContent }}</p>
          <!-- Mood stamp -->
          <div class="polaroid-stamp">{{ getMoodEmoji(selectedMood) }}</div>
        </div>

        <div class="polaroid-actions">
          <p class="polaroid-hint">卡片具有真实的物理噪点质感。</p>
          <el-button type="primary" color="#34d399" class="save-btn" @click="downloadPolaroid">
            导出高清图片
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft, ArrowRight, Check, EditPen, MagicStick, Picture,
} from '@element-plus/icons-vue'
import { diaryApi } from '@/api/diary'
import { photoApi } from '@/api/photos'
import type { CalendarCell, DiaryCalendarItem, MoodConfig, MoodType } from '@/types/diary'
import type { Photo } from '@/types/photo'

// ── Constants ─────────────────────────────────────────────────────────────────

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'] as const

const MOODS: MoodConfig[] = [
  { name: 'happy',    emoji: '😊', label: '开心',     color: '#fde047' },
  { name: 'calm',     emoji: '😌', label: '平静',     color: '#6ee7b7' },
  { name: 'energetic',emoji: '🤩', label: '元气满满', color: '#fdba74' },
  { name: 'tired',    emoji: '😮‍💨', label: '疲惫',   color: '#c4b5fd' },
  { name: 'sad',      emoji: '😔', label: '伤感',     color: '#93c5fd' },
]

const MOOD_EMOJI_MAP = Object.fromEntries(MOODS.map(m => [m.name, m.emoji])) as Record<MoodType, string>

// ── State ─────────────────────────────────────────────────────────────────────

const now = new Date()
const currentYear  = ref(now.getFullYear())
const currentMonth = ref(now.getMonth() + 1)

const monthEntries  = ref<Map<string, DiaryCalendarItem>>(new Map())
const loadingMonth  = ref(false)

const dialogVisible  = ref(false)
const polaroidVisible = ref(false)
const selectedDay    = ref(1)
const selectedMood   = ref<MoodType>('calm')
const selectedPhotoIds = ref<number[]>([])
const diaryContent   = ref('')
const isGenerating   = ref(false)
const isSaving       = ref(false)

// Photo picker
const pickerOpen     = ref(false)
const pickerPhotos   = ref<Photo[]>([])
const loadingPicker  = ref(false)

// ── Computed ──────────────────────────────────────────────────────────────────

/**
 * Geo text for the cover photo (first selected photo).
 * Returns "省·市" if available, null otherwise.
 */
const coverPhotoGeo = computed<string | null>(() => {
  if (selectedPhotoIds.value.length === 0) return null
  const coverId = selectedPhotoIds.value[0]
  const photo = pickerPhotos.value.find(p => p.id === coverId)
  if (!photo) return null
  const parts = [photo.province, photo.city].filter(Boolean)
  return parts.length > 0 ? parts.join('·') : null
})

/**
 * Build the 35-cell (5×7) calendar grid for the current month.
 * Padding cells from the previous / next month are included.
 */
const calendarCells = computed<CalendarCell[]>(() => {
  const year  = currentYear.value
  const month = currentMonth.value

  const firstDow = new Date(year, month - 1, 1).getDay()   // 0=Sun
  const daysInMonth = new Date(year, month, 0).getDate()
  const daysInPrev  = new Date(year, month - 1, 0).getDate()

  const cells: CalendarCell[] = []

  // Leading padding from previous month
  for (let i = firstDow - 1; i >= 0; i--) {
    cells.push({ day: daysInPrev - i, isPadding: true, diary: null })
  }

  // Current month days
  for (let d = 1; d <= daysInMonth; d++) {
    const key = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    cells.push({ day: d, isPadding: false, diary: monthEntries.value.get(key) ?? null })
  }

  // Trailing padding
  let trailingDay = 1
  while (cells.length % 7 !== 0) {
    cells.push({ day: trailingDay++, isPadding: true, diary: null })
  }

  return cells
})

// ── Helpers ───────────────────────────────────────────────────────────────────

/** @returns true if `day` is today in the currently viewed month */
function isToday(day: number): boolean {
  const t = new Date()
  return (
    currentYear.value === t.getFullYear() &&
    currentMonth.value === t.getMonth() + 1 &&
    day === t.getDate()
  )
}

function getMoodEmoji(mood: MoodType): string {
  return MOOD_EMOJI_MAP[mood] ?? '📝'
}

function isoDate(day: number): string {
  return `${currentYear.value}-${String(currentMonth.value).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

// ── Data loading ──────────────────────────────────────────────────────────────

async function loadMonth(): Promise<void> {
  loadingMonth.value = true
  try {
    const { data } = await diaryApi.getMonth(currentYear.value, currentMonth.value)
    const map = new Map<string, DiaryCalendarItem>()
    for (const entry of data.entries) {
      map.set(entry.diary_date, entry)
    }
    monthEntries.value = map
  } catch {
    ElMessage.error('日记数据加载失败')
  } finally {
    loadingMonth.value = false
  }
}

// ── Navigation ────────────────────────────────────────────────────────────────

function prevMonth(): void {
  if (currentMonth.value === 1) {
    currentMonth.value = 12
    currentYear.value--
  } else {
    currentMonth.value--
  }
  loadMonth()
}

function nextMonth(): void {
  if (currentMonth.value === 12) {
    currentMonth.value = 1
    currentYear.value++
  } else {
    currentMonth.value++
  }
  loadMonth()
}

function goToday(): void {
  const t = new Date()
  currentYear.value  = t.getFullYear()
  currentMonth.value = t.getMonth() + 1
  loadMonth()
}

// ── Dialog open / close ───────────────────────────────────────────────────────

async function openDialog(day: number, existing: DiaryCalendarItem | null): Promise<void> {
  selectedDay.value    = day
  pickerOpen.value     = false

  if (existing) {
    selectedMood.value = existing.mood
    diaryContent.value = existing.summary ?? ''
    // Fetch full diary entry to load associated photo_ids
    try {
      const { data } = await diaryApi.getByDate(isoDate(day))
      selectedPhotoIds.value = data.photo_ids
    } catch {
      selectedPhotoIds.value = []
    }
  } else {
    selectedMood.value     = 'calm'
    diaryContent.value     = ''
    selectedPhotoIds.value = []
  }
  dialogVisible.value = true
}

function deselectPhoto(photoId: number): void {
  selectedPhotoIds.value = selectedPhotoIds.value.filter(id => id !== photoId)
}

/** Toggle the inline photo picker and lazy-load photos on first open. */
async function togglePicker(): Promise<void> {
  pickerOpen.value = !pickerOpen.value
  if (pickerOpen.value && pickerPhotos.value.length === 0) {
    loadingPicker.value = true
    try {
      const { data } = await photoApi.list({ page_size: 80, sort_by: 'taken_at', order: 'desc' })
      pickerPhotos.value = data.items
    } catch {
      ElMessage.error('加载照片列表失败')
    } finally {
      loadingPicker.value = false
    }
  }
}

/** Toggle a photo in/out of the selection. */
function togglePickerPhoto(id: number): void {
  const idx = selectedPhotoIds.value.indexOf(id)
  if (idx === -1) {
    selectedPhotoIds.value.push(id)
  } else {
    selectedPhotoIds.value.splice(idx, 1)
  }
}

// ── AI draft ──────────────────────────────────────────────────────────────────

async function triggerAI(): Promise<void> {
  isGenerating.value = true
  diaryContent.value = ''
  try {
    const { data } = await diaryApi.generateDraft({
      diary_date: isoDate(selectedDay.value),
      photo_ids: selectedPhotoIds.value,
      mood: selectedMood.value,
    })
    // Typewriter effect
    let i = 0
    const text = data.draft
    const interval = setInterval(() => {
      diaryContent.value += text.charAt(i++)
      if (i >= text.length) clearInterval(interval)
    }, 25)
  } catch (err: any) {
    const msg = err?.response?.data?.detail ?? 'AI 主笔失败，请检查设置页的 AI 配置'
    ElMessage.error(msg)
  } finally {
    isGenerating.value = false
  }
}

// ── Save diary ────────────────────────────────────────────────────────────────

async function saveDiary(): Promise<void> {
  isSaving.value = true
  try {
    await diaryApi.save({
      diary_date: isoDate(selectedDay.value),
      content: diaryContent.value || null,
      mood: selectedMood.value,
      photo_ids: selectedPhotoIds.value,
    })
    ElMessage.success('日记及照片关联已保存')
    dialogVisible.value = false
    // Refresh calendar
    await loadMonth()
    // Show Polaroid if we have content
    if (diaryContent.value.trim()) {
      setTimeout(() => { polaroidVisible.value = true }, 400)
    }
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    isSaving.value = false
  }
}

// ── Polaroid export ────────────────────────────────────────────────────────────

function downloadPolaroid(): void {
  ElMessage.success('已调用 html2canvas 生成高清图片（需集成 html2canvas 库）')
  setTimeout(() => { polaroidVisible.value = false }, 1500)
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────

onMounted(() => { loadMonth() })
</script>

<style lang="scss" scoped>
// ── Page layout ───────────────────────────────────────────────────────────────
.diary-page {
  padding: 0;
}

// ── Header ────────────────────────────────────────────────────────────────────
.diary-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 28px;
}

.diary-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--no-text-primary);
  margin: 0 0 4px;
  line-height: 1.3;
}

.diary-subtitle {
  font-size: 13px;
  color: var(--no-text-muted);
  margin: 0;
}

.diary-nav {
  display: flex;
  align-items: center;
  gap: 16px;
}

.diary-month-label {
  font-size: 15px;
  font-weight: 500;
  color: var(--no-text-primary);
}

// ── Weekday row ───────────────────────────────────────────────────────────────
.calendar-weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 8px;
  margin-bottom: 8px;

  > div {
    text-align: center;
    font-size: 12px;
    font-weight: 500;
    color: var(--no-text-muted);
    padding: 4px 0;
  }
}

// ── Calendar grid ─────────────────────────────────────────────────────────────
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 8px;
}

.calendar-cell {
  position: relative;
  aspect-ratio: 1 / 1;
  border-radius: 12px;
  background-color: var(--no-bg-card);
  // 轻微暗色手账纸张底纹，让空格子不那么平板
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.025'/%3E%3C/svg%3E");
  border: 1px solid var(--no-border-low);
  overflow: hidden;
  cursor: pointer;
  transition: transform 300ms cubic-bezier(0.25, 0.8, 0.25, 1),
              box-shadow 300ms ease;

  &:hover:not(.is-padding) {
    transform: scale(1.04);
    z-index: 10;
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.45);
  }

  &.is-padding {
    cursor: default;
    opacity: 0.3;

    &:hover { transform: none; box-shadow: none; }
  }

  &.is-today .cell-day-num:not(.cell-day-over-photo) {
    color: var(--no-accent);
    font-weight: 700;
  }
}

// ── Cell internals ────────────────────────────────────────────────────────────
.cell-day-num {
  position: absolute;
  top: 8px;
  left: 10px;
  font-size: 15px;
  font-weight: 500;
  color: var(--no-text-secondary);
  z-index: 2;
  line-height: 1;
}

.cell-day-muted {
  color: var(--no-text-disabled);
  font-size: 13px;
}

.cell-today-badge {
  background: var(--no-accent);
  color: var(--no-bg-main) !important;
  border-radius: 50%;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px !important;
  top: 6px;
  left: 8px;
}

.cell-empty-hint {
  position: absolute;
  bottom: 10px;
  right: 10px;
  opacity: 0.3;
}

.cell-cover {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  background-color: var(--no-bg-hover);
}

.cell-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(to bottom, transparent 35%, rgba(0, 0, 0, 0.65) 100%);
  pointer-events: none;
}

.cell-day-over-photo {
  color: #fff;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.6);
}

.cell-mood-badge {
  position: absolute;
  bottom: 8px;
  right: 8px;
  font-size: 18px;
  z-index: 2;
  filter: drop-shadow(0 1px 2px rgba(0,0,0,0.5));
}

// Hover slide-up panel (Safari 兼容：圆角裁剪防黑边溢出)
.cell-hover-panel {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 10px;
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0) 0%, rgba(0, 0, 0, 0.82) 100%);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  // 强制在父容器圆角内剪裁，修复 Safari 黑边
  border-radius: 0 0 12px 12px;
  transform: translateY(101%); // 101% 避免 1px 残影
  transition: transform 280ms cubic-bezier(0.25, 0.8, 0.25, 1),
              opacity 200ms ease;
  opacity: 0;
  z-index: 3;
}

.calendar-cell:hover .cell-hover-panel {
  transform: translateY(0);
  opacity: 1;
}

// (hover rule moved inside .cell-hover-panel block above)

.cell-summary {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 12px;
  color: #fff;
  line-height: 1.5;
}

// ── Dialog base ───────────────────────────────────────────────────────────────
:deep(.diary-dialog) {
  .el-dialog__header {
    border-bottom: 1px solid var(--no-border-low);
    margin-right: 0;
    padding-bottom: 16px;
  }
}

// ── Write-diary dialog body ───────────────────────────────────────────────────
.dialog-body {
  display: flex;
  gap: 24px;
  height: 500px;
}

// ── Left: photo panel ─────────────────────────────────────────────────────────
.dialog-photo-panel {
  width: 41.6%;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--no-border-low);
  padding-right: 24px;
  overflow: hidden;
}

.panel-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: var(--no-text-muted);
  margin-bottom: 10px;
}

.panel-link {
  color: var(--el-color-primary);
  cursor: pointer;
  font-size: 12px;

  &:hover { text-decoration: underline; }
}

// ── Inline picker ─────────────────────────────────────────────────────────────
.picker-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px;
  max-height: 180px;
  overflow-y: auto;
  margin-bottom: 10px;
  padding: 4px;
  border: 1px solid var(--no-border-low);
  border-radius: 8px;
  background: var(--no-bg-main);

  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-thumb { background: var(--no-border-mid); border-radius: 2px; }
}

.picker-thumb {
  position: relative;
  aspect-ratio: 1;
  border-radius: 5px;
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
  transition: border-color 0.15s, opacity 0.15s;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  &:hover { opacity: 0.8; }

  &.is-selected {
    border-color: var(--no-accent);
  }
}

.picker-check {
  position: absolute;
  top: 3px;
  right: 3px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--no-accent);
  display: flex;
  align-items: center;
  justify-content: center;
}

.picker-empty {
  grid-column: 1 / -1;
  text-align: center;
  padding: 20px;
  color: var(--no-text-disabled);
  font-size: 13px;
}

// Picker slide transition
.picker-slide-enter-active,
.picker-slide-leave-active {
  transition: max-height 0.25s ease, opacity 0.2s ease;
  overflow: hidden;
}
.picker-slide-enter-from,
.picker-slide-leave-to {
  max-height: 0;
  opacity: 0;
}
.picker-slide-enter-to,
.picker-slide-leave-from {
  max-height: 200px;
  opacity: 1;
}

// ── Photo strip ───────────────────────────────────────────────────────────────
.photo-strip {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  overflow-x: auto;
  padding-bottom: 4px;

  &::-webkit-scrollbar { height: 4px; }
  &::-webkit-scrollbar-thumb { background: var(--no-border-mid); border-radius: 2px; }
}

.photo-thumb {
  position: relative;
  width: 60px;
  height: 60px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
  cursor: pointer;
  border: 2px solid var(--no-accent);

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.thumb-check {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 16px;
  height: 16px;
  background: var(--no-accent);
  border-radius: 50%;
  border: 2px solid var(--no-bg-card);
  display: flex;
  align-items: center;
  justify-content: center;
}

.photo-empty-hint {
  font-size: 12px;
  color: var(--no-text-disabled);
  display: flex;
  align-items: center;
  padding: 4px 0;
}

.cover-preview {
  flex: 1;
  border-radius: 12px;
  background-size: cover;
  background-position: center;
  background-color: var(--no-bg-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  position: relative;  // needed for geo overlay
}

.cover-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--no-text-disabled);
  font-size: 13px;
}

// ── Geo tag overlay ────────────────────────────────────────────────────────
.cover-geo-tag {
  position: absolute;
  bottom: 10px;
  left: 10px;
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px 4px 7px;
  background: rgba(21, 23, 26, 0.82);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-radius: 6px;
  border: 1px solid rgba(52, 211, 153, 0.2);
  pointer-events: none;
}

.cover-geo-pin {
  font-size: 12px;
  line-height: 1;
}

.cover-geo-text {
  font-size: 11px;
  font-weight: 500;
  color: #e5e7eb;
  letter-spacing: 0.02em;
}

.cover-geo-badge {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(52, 211, 153, 0.12);
  color: var(--no-accent);
  font-family: var(--no-font-mono);
  letter-spacing: 0.04em;
}

// ── Right: write panel ────────────────────────────────────────────────────────
.dialog-write-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.mood-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--no-bg-hover);
  border: 1px solid var(--no-border-low);
  border-radius: 10px;
  margin-bottom: 12px;
}

.panel-label-sm {
  font-size: 13px;
  color: var(--no-text-muted);
}

.mood-pills {
  display: flex;
  gap: 8px;
}

.mood-pill {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid var(--no-border-mid);
  background: transparent;
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s, background-color 0.2s, border-color 0.2s;

  &:hover { transform: scale(1.15); }

  &.active {
    border-color: transparent;
    transform: scale(1.15);
  }
}

.write-area-wrap {
  flex: 1;
  position: relative;
  margin-bottom: 12px;
  min-height: 0;
}

.write-textarea {
  width: 100%;
  height: 100%;
  resize: none;
  background: transparent;
  border: none;
  outline: none;
  color: var(--no-text-primary);
  font-size: 15px;
  line-height: 1.7;
  font-family: "Kaiti SC", "STKaiti", "KaiTi", "Brush Script MT", cursive, var(--no-font-base);
  padding: 4px;
  box-sizing: border-box;

  &::placeholder { color: var(--no-text-disabled); font-family: var(--no-font-base); }

  &::-webkit-scrollbar { width: 4px; }
  &::-webkit-scrollbar-thumb { background: var(--no-border-mid); border-radius: 2px; }
}

// Generating overlay
.generating-overlay {
  position: absolute;
  inset: 0;
  background: rgba(21, 23, 26, 0.85);
  backdrop-filter: blur(6px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  border-radius: 8px;
  z-index: 10;
}

.spinner {
  width: 30px;
  height: 30px;
  border: 3px solid #8b5cf6;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.generating-text {
  font-size: 14px;
  color: var(--no-text-primary);
  animation: pulse 1.5s ease-in-out infinite;
  font-family: "Kaiti SC", "STKaiti", cursive;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

// Transition
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

// Dialog action bar
.dialog-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.action-right {
  display: flex;
  gap: 10px;
  align-items: center;
}

// AI aurora button — shimmer breathing effect
.ai-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  border-radius: 8px;
  border: none;
  background: linear-gradient(135deg, #8b5cf6 0%, #d946ef 50%, #ec4899 100%);
  background-size: 200% 200%;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  animation: ai-shimmer 4s ease infinite;
  transition: transform 0.2s, box-shadow 0.2s, filter 0.2s;

  &:hover:not(:disabled) {
    transform: translateY(-1px);
    filter: brightness(1.15);
    box-shadow: 0 0 20px rgba(236, 72, 153, 0.5);
  }

  &:disabled { opacity: 0.5; cursor: not-allowed; animation: none; }
}

@keyframes ai-shimmer {
  0%   { background-position: 0% 50%; }
  50%  { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

.save-btn {
  color: var(--no-bg-main) !important;
}

// ── Polaroid ──────────────────────────────────────────────────────────────────
.polaroid-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 0;
}

.polaroid-card {
  width: 340px;
  background-color: #fefefc;
  // 更精细的纸张噪点（opacity 降低，更真实）
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.05'/%3E%3C/svg%3E");
  box-shadow: 0 25px 60px rgba(0, 0, 0, 0.65);
  border-radius: 3px;
  padding: 20px 20px 52px;
  // 手写墨水感：蓝黑色调
  color: #1e2230;
  position: relative;
}

.polaroid-photo {
  width: 100%;
  aspect-ratio: 1 / 1;
  background-size: cover;
  background-position: center;
  background-color: #222;
  box-shadow: inset 0 0 8px rgba(0, 0, 0, 0.15);
  border-radius: 3px;
  margin-bottom: 14px;
}

.polaroid-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.polaroid-date {
  font-size: 13px;
  font-style: italic;
  color: #888;
  font-family: serif;
}

.polaroid-location {
  font-size: 12px;
  color: #888;
}

.polaroid-content {
  font-size: 15px;
  line-height: 1.8;
  // 与 polaroid-card color 同步：墨蓝色手写感
  color: #1e2230;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin: 0;
  font-family: "Kaiti SC", "STKaiti", "KaiTi", cursive;
  letter-spacing: 0.5px;
}

.polaroid-stamp {
  position: absolute;
  bottom: 12px;
  right: 14px;
  font-size: 20px;
  border: 2px dashed #f87171;
  border-radius: 50%;
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  // 背景微红，复古印章感
  background: rgba(248, 113, 113, 0.06);
  color: #f87171;
  opacity: 0.65;
  transform: rotate(-12deg);
}

.polaroid-actions {
  text-align: center;
  margin-top: 24px;
}

.polaroid-hint {
  font-size: 13px;
  color: var(--no-text-muted);
  margin: 0 0 16px;
}
</style>
