<script setup lang="ts">
/**
 * ExportDialog.vue
 * Universal export dialog for photos (batch) and albums (single or batch).
 *
 * Usage:
 *   <ExportDialog v-model="show" mode="photos" :photo-ids="selectedIds" />
 *   <ExportDialog v-model="show" mode="album"  :album-id="42" album-title="旅行" />
 *   <ExportDialog v-model="show" mode="albums" :album-ids="[1,2,3]" />
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  downloadPhotosZip,
  downloadAlbumZip,
  downloadAlbumsZip,
} from '@/api/transfer'

// ── Props / Emits ─────────────────────────────────────────────────────────────

const props = withDefaults(defineProps<{
  modelValue: boolean
  /** "photos" | "album" | "albums" */
  mode: 'photos' | 'album' | 'albums'
  photoIds?: number[]
  albumId?: number
  albumTitle?: string
  albumIds?: number[]
}>(), {
  photoIds: () => [],
  albumIds: () => [],
  albumTitle: '相册',
})

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: v => emit('update:modelValue', v),
})

// ── State ─────────────────────────────────────────────────────────────────────

const filename   = ref('')
const loading    = ref(false)

const defaultFilename = computed(() => {
  const d = new Date().toISOString().slice(0, 10)
  if (props.mode === 'photos')  return `photos_${d}`
  if (props.mode === 'album')   return props.albumTitle || `album_${props.albumId}`
  return `albums_${d}`
})

const summary = computed(() => {
  if (props.mode === 'photos')  return `${props.photoIds!.length} 张照片`
  if (props.mode === 'album')   return `相册「${props.albumTitle}」全部照片`
  return `${props.albumIds!.length} 个相册`
})

// ── Actions ───────────────────────────────────────────────────────────────────

async function doExport() {
  const name = filename.value.trim() || defaultFilename.value
  loading.value = true
  try {
    if (props.mode === 'photos') {
      await downloadPhotosZip(props.photoIds!, name)
    } else if (props.mode === 'album') {
      await downloadAlbumZip(props.albumId!, name)
    } else {
      await downloadAlbumsZip(props.albumIds!, name)
    }
    ElMessage.success('ZIP 已开始下载')
    visible.value = false
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '导出失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="导出照片"
    width="420px"
    :close-on-click-modal="!loading"
    class="exp-dialog"
  >
    <div class="exp-body">
      <!-- Icon -->
      <div class="exp-icon">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
          <polyline points="7 10 12 15 17 10"/>
          <line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
      </div>

      <!-- Summary -->
      <p class="exp-summary">将 <strong>{{ summary }}</strong> 打包为 ZIP 文件下载到本地</p>

      <!-- Filename -->
      <el-form label-position="top" style="width: 100%">
        <el-form-item label="文件名">
          <el-input
            v-model="filename"
            :placeholder="defaultFilename"
            clearable
          >
            <template #append>.zip</template>
          </el-input>
        </el-form-item>
      </el-form>

      <!-- Tips -->
      <div class="exp-tips">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <span>导出原始文件，不压缩图片质量。大量照片可能需要较长时间。</span>
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false" :disabled="loading">取消</el-button>
      <el-button type="primary" :loading="loading" @click="doExport">
        开始导出
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.exp-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 8px 0 4px;
}

.exp-icon {
  width: 72px;
  height: 72px;
  border-radius: 16px;
  background: var(--el-color-primary-light-9);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-color-primary);
}

.exp-summary {
  font-size: 14px;
  color: var(--no-text-primary);
  text-align: center;
  margin: 0;
}

.exp-tips {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
  color: var(--no-text-muted);
  background: var(--no-bg-elevated);
  border-radius: 8px;
  padding: 10px 12px;
  width: 100%;
  box-sizing: border-box;

  svg { flex-shrink: 0; margin-top: 1px; }
}
</style>
