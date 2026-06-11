<template>
  <div class="db-root">

    <!-- ── Page header ─────────────────────────────────────────────── -->
    <div class="db-header">
      <div>
        <h1 class="db-title">概览仪表盘</h1>
        <p class="db-subtitle">你的所有记忆数据均安全地运行在本地网络。</p>
      </div>
      <div class="db-header-actions">
        <el-button :icon="RefreshRight" circle :loading="refreshing" @click="refresh" />
        <el-button type="primary" @click="triggerScan">
          <el-icon><Refresh /></el-icon>
          增量扫描
        </el-button>
      </div>
    </div>

    <!-- ── Active scan progress ────────────────────────────────────── -->
    <ScanProgress v-if="scanStore.activeTask" :task="scanStore.activeTask" class="db-scan-progress" />

    <!-- ── Stat cards ──────────────────────────────────────────────── -->
    <div class="db-stats-grid">
      <!-- Total photos -->
      <el-card class="db-stat-card hover-card" :body-style="{ padding: '20px' }">
        <div class="db-stat-head">
          <span class="db-stat-label">总照片数</span>
          <div class="db-stat-icon">
            <el-icon><PictureFilled /></el-icon>
          </div>
        </div>
        <div class="db-stat-value font-mono">
          {{ stats ? stats.total_photos.toLocaleString() : '—' }}
        </div>
        <div class="db-stat-hint db-stat-hint--accent">
          <el-icon><ArrowUpBold /></el-icon>
          {{ stats ? `${stats.blurry_count} 张模糊` : '加载中…' }}
        </div>
      </el-card>

      <!-- Storage -->
      <el-card class="db-stat-card hover-card" :body-style="{ padding: '20px' }">
        <div class="db-stat-head">
          <span class="db-stat-label">存储占用</span>
          <div class="db-stat-icon">
            <el-icon><Coin /></el-icon>
          </div>
        </div>
        <div class="db-stat-value font-mono">
          {{ stats ? formatBytes(stats.total_size_bytes) : '—' }}
        </div>
        <div class="db-stat-hint">
          {{ stats ? `欠曝 ${stats.underexposed_count} · 过曝 ${stats.overexposed_count}` : '' }}
        </div>
      </el-card>

      <!-- People -->
      <el-card class="db-stat-card hover-card" :body-style="{ padding: '20px' }">
        <div class="db-stat-head">
          <span class="db-stat-label">识别人物</span>
          <div class="db-stat-icon">
            <el-icon><UserFilled /></el-icon>
          </div>
        </div>
        <div class="db-stat-value font-mono">—</div>
        <div class="db-stat-hint db-stat-hint--accent">DBSCAN 聚类已完成</div>
      </el-card>

      <!-- Cleanup warning -->
      <el-card class="db-stat-card db-stat-card--warn hover-card" :body-style="{ padding: '20px' }">
        <div class="db-stat-head">
          <span class="db-stat-label db-stat-label--warn">建议清理去重</span>
          <div class="db-stat-icon db-stat-icon--warn">
            <el-icon><Delete /></el-icon>
          </div>
        </div>
        <div class="db-stat-value db-stat-value--warn font-mono">
          {{ stats ? formatBytes(stats.reclaimable_bytes) : '—' }}
        </div>
        <div class="db-stat-hint db-stat-hint--warn">
          发现 {{ stats?.duplicate_count ?? '—' }} 组相似照片
        </div>
      </el-card>
    </div>

    <!-- ── Lower two-column section ────────────────────────────────── -->
    <div class="db-lower">

      <!-- Left: recent top photos -->
      <div class="db-section">
        <div class="db-section-head">
          <h2 class="db-section-title">近期绝佳抓拍</h2>
          <span class="soft-badge">AI 优选</span>
        </div>
        <div class="db-top-photos">
          <div
            v-for="photo in topPhotos"
            :key="photo.id"
            class="db-top-cell"
            @click="openViewer(photo)"
          >
            <img
              :src="`/api/v1/thumbnails/${photo.id}?size=256`"
              :alt="photo.file_name"
              loading="lazy"
              class="db-top-img"
              @error="onImgErr"
            />
            <div class="db-top-overlay">
              <span class="db-top-score">AI {{ topScore(photo) }}</span>
            </div>
          </div>
          <!-- Placeholders when no photos loaded -->
          <div v-if="topPhotos.length === 0" v-for="i in 3" :key="i" class="db-top-cell db-top-placeholder">
            <el-icon size="32"><PictureFilled /></el-icon>
          </div>
        </div>
      </div>

      <!-- Right: system tasks -->
      <div class="db-section db-section--tasks">
        <h2 class="db-section-title">系统任务</h2>
        <el-card shadow="never" class="db-tasks-card" :body-style="{ padding: '0' }">

          <!-- Active scan task -->
          <div v-if="scanStore.activeTask" class="db-task-item">
            <el-icon class="db-task-icon db-task-icon--info"><Loading /></el-icon>
            <div class="db-task-body">
              <div class="db-task-name">{{ scanStore.activeTask.scan_path }}</div>
              <el-progress
                :percentage="scanProgress"
                :stroke-width="4"
                :show-text="false"
                color="var(--no-info)"
              />
            </div>
            <span class="db-task-pct font-mono">{{ scanProgress }}%</span>
          </div>

          <div class="db-task-item" :class="{ 'db-task-item--done': !!stats?.last_scan_at }">
            <el-icon class="db-task-icon" :class="stats?.last_scan_at ? 'db-task-icon--done' : 'db-task-icon--muted'">
              <CircleCheck v-if="stats?.last_scan_at" /><Loading v-else />
            </el-icon>
            <div class="db-task-body">
              <div class="db-task-name">
                {{ stats?.last_scan_at ? `上次扫描完成` : '等待首次扫描' }}
              </div>
              <div v-if="stats?.last_scan_at" class="db-task-sub font-mono">
                {{ formatDate(stats.last_scan_at) }}
              </div>
            </div>
          </div>

          <div class="db-task-item db-task-item--muted">
            <el-icon class="db-task-icon db-task-icon--muted"><VideoPause /></el-icon>
            <div class="db-task-body">
              <div class="db-task-name">pHash 去重比对</div>
              <div class="db-task-sub">等待空闲时间</div>
            </div>
          </div>

        </el-card>

        <!-- Last scan path -->
        <div v-if="stats?.last_scan_path" class="db-last-scan font-mono">
          <el-icon><FolderOpened /></el-icon>
          {{ stats.last_scan_path }}
        </div>
      </div>

    </div>

    <!-- ── Image viewer ────────────────────────────────────────────── -->
    <ImageViewer
      :visible="!!viewerPhoto"
      :photo="viewerPhoto"
      :has-prev="false"
      :has-next="false"
      @close="viewerPhoto = null"
      @navigate="() => {}"
      @soft-delete="() => {}"
      @toast="() => {}"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'
import { dashboardApi, type DashboardStats } from '@/api/dashboard'
import { useScanStore } from '@/stores/useScanStore'
import { usePhotoStore } from '@/stores/usePhotoStore'
import ScanProgress from '@/components/common/ScanProgress.vue'
import ImageViewer from '@/components/gallery/ImageViewer.vue'
import { formatBytes, formatDate } from '@/utils/format'
import type { Photo } from '@/types/photo'

const stats = ref<DashboardStats | null>(null)
const scanStore = useScanStore()
const photoStore = usePhotoStore()
const refreshing = ref(false)
const viewerPhoto = ref<Photo | null>(null)

/** Top 3 photos by sharpness score */
const topPhotos = computed<Photo[]>(() => {
  return [...photoStore.photos]
    .filter((p) => p.scores?.sharpness_score != null)
    .sort((a, b) => (b.scores?.sharpness_score ?? 0) - (a.scores?.sharpness_score ?? 0))
    .slice(0, 3)
})

function topScore(p: Photo): string {
  const s = p.scores?.sharpness_score
  if (s == null) return 'N/A'
  return Math.min(10, (s / 3000) * 10).toFixed(1)
}

const scanProgress = computed<number>(() => {
  const t = scanStore.activeTask
  if (!t || !t.total_files || t.total_files === 0) return 0
  return Math.round(((t.processed_files ?? 0) / t.total_files) * 100)
})

onMounted(async () => {
  await Promise.all([
    dashboardApi.stats().then(({ data }) => { stats.value = data }),
    scanStore.fetchTasks(),
    photoStore.fetchPage(true),
  ])
})

async function refresh() {
  refreshing.value = true
  try {
    const { data } = await dashboardApi.stats()
    stats.value = data
    await scanStore.fetchTasks()
  } finally {
    refreshing.value = false
  }
}

async function triggerScan() {
  ElMessage({ message: '已触发后台增量扫描任务', type: 'success' })
  await scanStore.fetchTasks()
}

function openViewer(photo: Photo) {
  viewerPhoto.value = photo
}

function onImgErr(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.opacity = '0.2'
}
</script>

<style scoped lang="scss">
/* ── Root ────────────────────────────────────────────────────────────── */
.db-root {
  display: flex;
  flex-direction: column;
  gap: 32px;
  padding-bottom: 32px;
}

/* ── Header ──────────────────────────────────────────────────────────── */
.db-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}
.db-title {
  font-size: 24px; font-weight: 600;
  letter-spacing: -0.02em; margin: 0 0 4px;
  color: var(--no-text-primary);
}
.db-subtitle {
  font-size: 13px; color: var(--no-text-secondary); margin: 0;
}
.db-header-actions {
  display: flex; gap: 10px; align-items: center;
}
.db-scan-progress { margin-top: -16px; }

/* ── Stats grid ──────────────────────────────────────────────────────── */
.db-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;

  @media (max-width: 1100px) {
    grid-template-columns: repeat(2, 1fr);
  }
  @media (max-width: 600px) {
    grid-template-columns: 1fr;
  }
}

.db-stat-card {
  cursor: pointer;

  &--warn {
    border-color: rgba(251, 191, 36, 0.25) !important;
    background-color: rgba(251, 191, 36, 0.04) !important;

    &:hover {
      border-color: rgba(251, 191, 36, 0.45) !important;
      background-color: rgba(251, 191, 36, 0.08) !important;
    }
  }
}

.db-stat-head {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 10px;
}
.db-stat-label {
  font-size: 13px; color: var(--no-text-secondary);
  &--warn { color: rgba(251, 191, 36, 0.8); }
}
.db-stat-icon {
  width: 32px; height: 32px;
  border-radius: 6px;
  background: var(--no-bg-card-hover);
  color: var(--no-text-secondary);
  display: flex; align-items: center; justify-content: center;

  &--warn {
    background: rgba(251, 191, 36, 0.12);
    color: rgba(251, 191, 36, 0.9);
  }
}
.db-stat-value {
  font-size: 28px; font-weight: 500;
  color: var(--no-text-primary);
  line-height: 1.15;
  margin-bottom: 8px;

  &--warn { color: rgba(251, 191, 36, 0.9); }
}
.db-stat-hint {
  font-size: 12px; color: var(--no-text-muted);
  display: flex; align-items: center; gap: 4px;

  &--accent { color: var(--no-accent); }
  &--warn   { color: rgba(251, 191, 36, 0.8); }
}

/* ── Lower section ───────────────────────────────────────────────────── */
.db-lower {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 24px;

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
}

.db-section { display: flex; flex-direction: column; gap: 16px; }
.db-section-head {
  display: flex; align-items: center; gap: 10px;
}
.db-section-title {
  font-size: 18px; font-weight: 500;
  color: var(--no-text-primary); margin: 0;
}

/* ── Top photos ──────────────────────────────────────────────────────── */
.db-top-photos {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.db-top-cell {
  aspect-ratio: 4 / 3;
  border-radius: var(--no-radius-btn);
  background: var(--no-bg-card-hover);
  border: 1px solid var(--no-border-low);
  overflow: hidden;
  position: relative;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;

  &:hover {
    border-color: var(--no-accent);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4);
  }
}
.db-top-img {
  width: 100%; height: 100%;
  object-fit: cover;
  transition: transform 0.5s;
  .db-top-cell:hover & { transform: scale(1.05); }
}
.db-top-overlay {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  padding: 6px 8px;
  background: linear-gradient(to top, rgba(14,15,17,0.85), transparent);
  opacity: 0; transition: opacity 0.2s;
  .db-top-cell:hover & { opacity: 1; }
}
.db-top-score {
  font-size: 10px; font-family: var(--no-font-mono);
  color: var(--no-accent); font-weight: 600;
}
.db-top-placeholder {
  display: flex; align-items: center; justify-content: center;
  color: var(--no-text-muted);
  cursor: default;
  &:hover { border-color: var(--no-border-low); box-shadow: none; }
}

/* ── Tasks card ──────────────────────────────────────────────────────── */
.db-tasks-card { flex: 1; }

.db-task-item {
  padding: 14px 16px;
  border-bottom: 1px solid var(--no-border-low);
  display: flex; align-items: center; gap: 12px;

  &:last-child { border-bottom: none; }
  &--muted { opacity: 0.45; }
}

.db-task-icon {
  font-size: 16px; flex-shrink: 0;

  &--info { color: var(--no-info); }
  &--done { color: var(--no-accent); }
  &--muted { color: var(--no-text-muted); }
}
.db-task-body { flex: 1; min-width: 0; }
.db-task-name {
  font-size: 13px; color: var(--no-text-primary);
  margin-bottom: 4px;
}
.db-task-sub {
  font-size: 11px; color: var(--no-text-secondary);
}
.db-task-pct {
  font-size: 11px; color: var(--no-text-secondary); flex-shrink: 0;
}

.db-last-scan {
  font-size: 11px; color: var(--no-text-muted);
  display: flex; align-items: center; gap: 6px;
  padding: 4px 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* ── Utilities ───────────────────────────────────────────────────────── */
.font-mono { font-family: var(--no-font-mono); }
</style>
