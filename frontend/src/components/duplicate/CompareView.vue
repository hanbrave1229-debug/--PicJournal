<template>
  <div class="compare-view">
    <div
      v-for="photo in group.photos"
      :key="photo.id"
      class="compare-item"
      :class="{
        'is-recommended': photo.id === group.recommended_keep_id,
        'is-selected-keep': keepIds.includes(photo.id),
        'is-selected-delete': deleteIds.includes(photo.id),
      }"
    >
      <img
        :src="photoApi.thumbnailUrl(photo.id, 1080)"
        :alt="photo.file_name"
        class="compare-img"
      />

      <div class="compare-meta">
        <div class="meta-row">
          <span class="meta-label">文件名</span>
          <span class="meta-value">{{ photo.file_name }}</span>
        </div>
        <div class="meta-row">
          <span class="meta-label">尺寸</span>
          <span class="meta-value" :class="{ highlight: isMax(photo, 'resolution') }">
            {{ formatDimensions(photo.width, photo.height) }}
          </span>
        </div>
        <div class="meta-row">
          <span class="meta-label">大小</span>
          <span class="meta-value" :class="{ highlight: isMax(photo, 'size') }">
            {{ formatBytes(photo.file_size) }}
          </span>
        </div>
        <div class="meta-row">
          <span class="meta-label">清晰度</span>
          <span
            class="meta-value"
            :style="{ color: sharpnessColor(photo.scores.sharpness_score) }"
          >
            {{ sharpnessLabel(photo.scores.sharpness_score) }}
            <small v-if="photo.scores.sharpness_score != null">
              ({{ photo.scores.sharpness_score.toFixed(0) }})
            </small>
          </span>
        </div>
        <div class="meta-row">
          <span class="meta-label">拍摄时间</span>
          <span class="meta-value">{{ formatDate(photo.exif.taken_at) }}</span>
        </div>
      </div>

      <div class="compare-actions">
        <el-tag v-if="photo.id === group.recommended_keep_id" type="success" size="small">
          推荐保留
        </el-tag>
        <div class="action-btns">
          <el-button
            size="small"
            type="success"
            plain
            :disabled="deleteIds.includes(photo.id)"
            @click="$emit('keep', photo.id)"
          >保留</el-button>
          <el-button
            size="small"
            type="danger"
            plain
            :disabled="keepIds.includes(photo.id)"
            @click="$emit('delete', photo.id)"
          >删除</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { photoApi } from '@/api/photos'
import { formatBytes, formatDate, formatDimensions } from '@/utils/format'
import { sharpnessColor, sharpnessLabel } from '@/utils/score'
import type { DuplicateGroup } from '@/types/duplicate'
import type { Photo } from '@/types/photo'

const props = defineProps<{
  group: DuplicateGroup
  keepIds: number[]
  deleteIds: number[]
}>()

defineEmits<{
  keep: [id: number]
  delete: [id: number]
}>()

function isMax(photo: Photo, type: 'resolution' | 'size'): boolean {
  if (type === 'resolution') {
    const maxRes = Math.max(...props.group.photos.map(p => (p.width ?? 0) * (p.height ?? 0)))
    return ((photo.width ?? 0) * (photo.height ?? 0)) === maxRes
  }
  const maxSize = Math.max(...props.group.photos.map(p => p.file_size))
  return photo.file_size === maxSize
}
</script>

<style scoped lang="scss">
.compare-view {
  display: flex;
  gap: 16px;
  overflow-x: auto;
  padding-bottom: 8px;
}

.compare-item {
  flex: 1;
  min-width: 200px;
  border: 2px solid var(--el-border-color);
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 0.2s;

  &.is-recommended { border-color: var(--el-color-success); }
  &.is-selected-keep { border-color: var(--el-color-success); background: var(--el-color-success-light-9); }
  &.is-selected-delete { border-color: var(--el-color-danger); opacity: 0.6; }
}

.compare-img {
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: cover;
  display: block;
  background: #f0f0f0;
}

.compare-meta {
  padding: 10px 12px;
  font-size: 12px;
}

.meta-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.meta-label { color: var(--el-text-color-placeholder); }
.meta-value { font-weight: 500; }
.highlight { color: var(--el-color-success); font-weight: 700; }

.compare-actions {
  padding: 8px 12px;
  border-top: 1px solid var(--el-border-color-lighter);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.action-btns { display: flex; gap: 6px; }
</style>
