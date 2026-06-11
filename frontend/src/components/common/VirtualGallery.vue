<template>
  <!--
    VirtualGallery — high-performance photo grid using @tanstack/vue-virtual.

    Only the visible rows (+ overscan buffer) are rendered in the DOM.
    All other rows are represented by empty height to keep the scrollbar accurate.
    This keeps the DOM node count constant regardless of library size,
    ensuring smooth 160 Hz scrolling even with 100k+ thumbnails.
  -->
  <div
    ref="containerRef"
    class="virtual-gallery"
    @scroll.passive="onScroll"
  >
    <!-- Total height spacer so the scrollbar is accurate -->
    <div :style="{ height: `${totalHeight}px`, position: 'relative' }">
      <div
        v-for="vRow in virtualRows"
        :key="vRow.index"
        class="gallery-row"
        :style="{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: `${itemHeight}px`,
          transform: `translateY(${vRow.start}px)`,
        }"
      >
        <div
          v-for="photo in rows[vRow.index]"
          :key="photo.id"
          class="gallery-cell"
          :class="{ 'is-duplicate': photo.duplicate_group_id != null }"
          @click="$emit('select', photo)"
        >
          <img
            :src="thumbnailUrl(photo.id)"
            :alt="photo.file_name"
            loading="lazy"
            class="gallery-thumb"
          />
          <div class="gallery-overlay">
            <span v-if="photo.duplicate_group_id" class="dup-badge">重复</span>
            <span
              class="sharpness-dot"
              :style="{ background: sharpnessColor(photo.scores.sharpness_score) }"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, toRef } from 'vue'
import { photoApi } from '@/api/photos'
import { useVirtualScroll } from '@/composables/useVirtualScroll'
import { sharpnessColor } from '@/utils/score'
import type { Photo } from '@/types/photo'

const props = withDefaults(defineProps<{
  /** Full photo list (all pages loaded so far) */
  photos: Photo[]
  /** Grid columns — caller computes from container width */
  columns?: number
  /** Row height in px */
  itemHeight?: number
}>(), {
  columns: 5,
  itemHeight: 220,
})

defineEmits<{
  /** Emitted when user clicks a photo card */
  select: [photo: Photo]
}>()

const { containerRef, rows, virtualRows, totalHeight } = useVirtualScroll({
  items: toRef(props, 'photos'),
  columns: computed(() => props.columns),
  itemHeight: props.itemHeight,
  overscan: 3,
})

function thumbnailUrl(id: number) {
  return photoApi.thumbnailUrl(id, 256)
}

/** Expose scroll container ref so parent can call scrollTop = 0 */
defineExpose({ containerRef })
</script>

<style scoped lang="scss">
.virtual-gallery {
  height: 100%;
  overflow-y: auto;
  will-change: transform; // GPU compositing layer — critical for 160 Hz displays
}

.gallery-row {
  display: flex;
  gap: 4px;
  padding: 2px 0;
}

.gallery-cell {
  flex: 1;
  position: relative;
  overflow: hidden;
  border-radius: 4px;
  cursor: pointer;
  background: #e8e8e8;
  transition: transform 0.15s ease;

  &:hover {
    transform: scale(1.02);
    z-index: 1;

    .gallery-overlay {
      opacity: 1;
    }
  }

  &.is-duplicate {
    outline: 2px solid var(--el-color-warning);
    outline-offset: -2px;
  }
}

.gallery-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.gallery-overlay {
  position: absolute;
  inset: 0;
  opacity: 0;
  transition: opacity 0.15s;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 6px;
  background: linear-gradient(to bottom, rgba(0,0,0,0.4) 0%, transparent 40%);
}

.dup-badge {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--el-color-warning);
  color: #fff;
  font-weight: 600;
}

.sharpness-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 1.5px solid rgba(255,255,255,0.8);
}
</style>
