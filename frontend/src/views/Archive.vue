<template>
  <div class="arc-page">
    <!-- Header -->
    <div class="arc-header">
      <div class="arc-header-left">
        <h1 class="arc-title">归档箱</h1>
        <p class="arc-subtitle">
          存放不想删除、但也不想在主时间轴显示的照片。物理文件绝对安全。
        </p>
      </div>
      <div class="arc-header-meta">
        <span class="arc-count-badge" v-if="total > 0">
          {{ total }} 张归档
        </span>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="!loading && photos.length === 0" class="arc-empty">
      <el-icon size="48" class="arc-empty-icon"><Box /></el-icon>
      <p class="arc-empty-title">归档箱为空</p>
      <p class="arc-empty-desc">
        在照片库中将不常用的照片「归档」，它们会在这里安静保存，随时可恢复。
      </p>
    </div>

    <!-- Grid -->
    <div v-else class="arc-grid" v-loading="loading">
      <div
        v-for="photo in photos"
        :key="photo.id"
        class="arc-card group"
      >
        <!-- Thumbnail -->
        <div class="arc-card-img-wrap">
          <img
            :src="`/api/v1/thumbnails/${photo.id}?size=256`"
            :alt="photo.file_name"
            class="arc-card-img"
            loading="lazy"
          />
          <!-- Hover overlay -->
          <div class="arc-card-overlay">
            <el-button
              size="small"
              type="success"
              plain
              :loading="restoringId === photo.id"
              @click.stop="handleUnarchive(photo)"
            >
              移出归档
            </el-button>
          </div>
        </div>

        <!-- Meta -->
        <div class="arc-card-meta">
          <span class="arc-card-name">{{ photo.file_name }}</span>
          <span class="arc-card-date" v-if="photo.exif?.taken_at">
            {{ formatDate(photo.exif.taken_at) }}
          </span>
          <!-- Geo tag -->
          <span class="arc-card-geo" v-if="photo.province || photo.city">
            📍 {{ [photo.province, photo.city].filter(Boolean).join('·') }}
          </span>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div class="arc-pagination" v-if="total > pageSize">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="loadArchive"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Box } from '@element-plus/icons-vue'
import { archiveApi } from '@/api/archive'
import type { Photo } from '@/types/photo'

const photos    = ref<Photo[]>([])
const total     = ref(0)
const page      = ref(1)
const pageSize  = 60
const loading   = ref(false)
const restoringId = ref<number | null>(null)

async function loadArchive(): Promise<void> {
  loading.value = true
  try {
    const { data } = await archiveApi.list({ page: page.value, page_size: pageSize })
    photos.value = data.items
    total.value  = data.total
  } catch {
    ElMessage.error('加载归档列表失败')
  } finally {
    loading.value = false
  }
}

async function handleUnarchive(photo: Photo): Promise<void> {
  restoringId.value = photo.id
  try {
    await archiveApi.unarchive(photo.id)
    photos.value = photos.value.filter(p => p.id !== photo.id)
    total.value--
    ElMessage.success('已恢复至主时间轴')
  } catch {
    ElMessage.error('恢复失败，请重试')
  } finally {
    restoringId.value = null
  }
}

/**
 * Format ISO date string to "YYYY.MM.DD"
 */
function formatDate(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`
}

onMounted(loadArchive)
</script>

<style lang="scss" scoped>
.arc-page {
  padding: 0;
}

// ── Header ────────────────────────────────────────────────────────────────────
.arc-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 28px;
}

.arc-header-left { flex: 1; }

.arc-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--no-text-primary);
  margin: 0 0 6px;
}

.arc-subtitle {
  font-size: 13px;
  color: var(--no-text-muted);
  margin: 0;
  line-height: 1.5;
}

.arc-count-badge {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 20px;
  background: rgba(96, 165, 250, 0.12);
  color: #60a5fa;
  border: 1px solid rgba(96, 165, 250, 0.2);
  font-weight: 500;
  white-space: nowrap;
}

// ── Empty state ───────────────────────────────────────────────────────────────
.arc-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 24px;
  border: 1px dashed var(--no-border-low);
  border-radius: 16px;
  text-align: center;
}

.arc-empty-icon {
  color: var(--no-text-muted);
  margin-bottom: 16px;
  opacity: 0.5;
}

.arc-empty-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--no-text-secondary);
  margin: 0 0 8px;
}

.arc-empty-desc {
  font-size: 13px;
  color: var(--no-text-muted);
  margin: 0;
  max-width: 400px;
  line-height: 1.6;
}

// ── Photo grid ────────────────────────────────────────────────────────────────
.arc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
  min-height: 200px;
}

.arc-card {
  border-radius: 10px;
  overflow: hidden;
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  transition: border-color 200ms ease;
  opacity: 0.85;

  &:hover {
    opacity: 1;
    border-color: rgba(96, 165, 250, 0.4);
  }
}

.arc-card-img-wrap {
  position: relative;
  aspect-ratio: 1;
  overflow: hidden;
  background: var(--no-bg-main);
}

.arc-card-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 300ms ease;

  .arc-card:hover & {
    transform: scale(1.03);
  }
}

.arc-card-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 200ms ease;

  .arc-card:hover & {
    opacity: 1;
  }
}

.arc-card-meta {
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.arc-card-name {
  font-size: 11px;
  color: var(--no-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.arc-card-date {
  font-size: 11px;
  color: var(--no-text-muted);
  font-family: var(--no-font-mono);
}

.arc-card-geo {
  font-size: 10px;
  color: var(--no-accent);
  opacity: 0.8;
}

// ── Pagination ────────────────────────────────────────────────────────────────
.arc-pagination {
  display: flex;
  justify-content: center;
  margin-top: 32px;
}
</style>
