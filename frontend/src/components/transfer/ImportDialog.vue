<script setup lang="ts">
/**
 * ImportDialog.vue
 * Three-tab import dialog:
 *   Tab 1 — Upload photo files (drag-drop + multi-select) → library
 *   Tab 2 — Upload ZIP album package → extract + create album
 *   Tab 3 — Pick from existing library → create album
 */
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile, UploadUserFile } from 'element-plus'
import {
  importPhotos,
  importAlbumFromZip,
  importAlbumFromLibrary,
  getScanRoot,
  type ImportPhotosResult,
} from '@/api/transfer'
import api from '@/api/index'
import type { Photo } from '@/types/photo'

// ── Props / Emits ─────────────────────────────────────────────────────────────

const props = defineProps<{
  modelValue: boolean
  /** Tabs to hide, e.g. ['library'] */
  hideTabs?: string[]
  /**
   * When set, dialog is in "add to existing album" mode:
   * - Only shows ZIP tab, no album_name input
   * - Calls POST /import/album/{albumId}/zip
   */
  albumId?: number
}>()
const emit  = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  /** Emitted when photos/albums were imported, so callers can refresh. */
  (e: 'imported', payload: { type: 'photos' | 'album'; scan_task_id?: number; album_id?: number }): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: v => emit('update:modelValue', v),
})

// ── Shared ────────────────────────────────────────────────────────────────────

const activeTab     = ref<'photos' | 'zip' | 'library'>('photos')
const loading       = ref(false)
const uploadPct     = ref(0)
const scanRoot      = ref<string | null>(null)

onMounted(async () => {
  const root = await getScanRoot()
  scanRoot.value = root
})

// ── Tab 1: Upload photos ──────────────────────────────────────────────────────

const photoFiles    = ref<UploadUserFile[]>([])
const photoSubdir   = ref('imported')
const photoResult   = ref<ImportPhotosResult | null>(null)

const photoDestPath = computed(() => {
  if (!scanRoot.value) return '（需先运行一次扫描）'
  const sub = photoSubdir.value.trim() || 'imported'
  return `${scanRoot.value}/PicJournal/${sub}/`
})

function handlePhotoDrop(rawFiles: File[]) {
  rawFiles.forEach(f => {
    photoFiles.value.push({ name: f.name, raw: f, uid: Date.now() + Math.random() } as UploadUserFile)
  })
}

async function doImportPhotos() {
  if (!photoFiles.value.length) {
    ElMessage.warning('请先选择照片文件')
    return
  }
  const raw = photoFiles.value.map(f => f.raw as File).filter(Boolean)
  if (!raw.length) return

  loading.value = true
  uploadPct.value = 0
  photoResult.value = null

  try {
    const result = await importPhotos(raw, photoSubdir.value.trim() || 'imported', pct => { uploadPct.value = pct })
    photoResult.value = result
    ElMessage.success(`已导入 ${result.saved} 张，正在扫描入库…`)
    emit('imported', { type: 'photos', scan_task_id: result.scan_task_id })
    photoFiles.value = []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '导入失败')
  } finally {
    loading.value = false
  }
}

// ── Tab 2: ZIP album ──────────────────────────────────────────────────────────

const zipFile       = ref<File | null>(null)
const zipAlbumName  = ref('')
const zipSubdir     = ref('')
const zipFileList   = ref<UploadUserFile[]>([])

function handleZipChange(file: UploadFile) {
  if (!file.raw?.name.toLowerCase().endsWith('.zip')) {
    ElMessage.warning('只支持 .zip 文件')
    zipFileList.value = []
    return
  }
  zipFile.value = file.raw as File
  if (!zipAlbumName.value) zipAlbumName.value = file.name.replace(/\.zip$/i, '')
}

async function doImportZip() {
  if (!zipFile.value) { ElMessage.warning('请先选择 ZIP 文件'); return }

  loading.value = true
  uploadPct.value = 0

  try {
    // albumId mode: POST /import/album/{albumId}/zip (no album_name required)
    if (props.albumId) {
      const formData = new FormData()
      formData.append('file', zipFile.value)
      // Do NOT set Content-Type manually — axios sets multipart/form-data with boundary automatically
      const { data: result } = await api.post(
        `/import/album/${props.albumId}/zip`,
        formData,
        {
          onUploadProgress: (e: ProgressEvent) => {
            if (e.total) uploadPct.value = Math.round((e.loaded / e.total) * 100)
          },
        },
      )
      ElMessage.success(`已导入 ${result.saved} 张照片，正在扫描入库…`)
      emit('imported', { type: 'album', album_id: result.album_id })
      zipFile.value = null
      zipFileList.value = []
      visible.value = false
      return
    }

    // Regular mode: create new album
    if (!zipAlbumName.value.trim()) { ElMessage.warning('请填写相册名称'); return }

    const result = await importAlbumFromZip(
      zipFile.value,
      zipAlbumName.value.trim(),
      zipSubdir.value.trim() || zipAlbumName.value.trim(),
      pct => { uploadPct.value = pct },
    )
    ElMessage.success(`相册「${result.album_name}」已创建，正在扫描 ${result.saved} 张照片…`)
    emit('imported', { type: 'album', album_id: result.album_id })
    zipFile.value = null
    zipFileList.value = []
    zipAlbumName.value = ''
    visible.value = false
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '导入失败')
  } finally {
    loading.value = false
  }
}

// ── Tab 3: From library ───────────────────────────────────────────────────────

const libraryPhotos   = ref<Photo[]>([])
const libraryLoading  = ref(false)
const libraryPage     = ref(1)
const libraryTotal    = ref(0)
const librarySelected = ref<number[]>([])
const newAlbumName    = ref('')

async function loadLibraryPhotos() {
  libraryLoading.value = true
  try {
    const res = await api.get<{ total: number; items: Photo[] }>('/photos', {
      params: { page: libraryPage.value, page_size: 60, sort_by: 'taken_at', order: 'desc' },
    })
    libraryPhotos.value  = res.data.items
    libraryTotal.value   = res.data.total
  } finally {
    libraryLoading.value = false
  }
}

watch(() => activeTab.value, (tab) => {
  if (tab === 'library' && !libraryPhotos.value.length) loadLibraryPhotos()
})

watch(libraryPage, loadLibraryPhotos)

function toggleSelect(id: number) {
  const idx = librarySelected.value.indexOf(id)
  if (idx === -1) librarySelected.value.push(id)
  else librarySelected.value.splice(idx, 1)
}

async function doImportFromLibrary() {
  if (!librarySelected.value.length) { ElMessage.warning('请先勾选照片'); return }
  if (!newAlbumName.value.trim()) { ElMessage.warning('请填写相册名称'); return }

  loading.value = true
  try {
    const result = await importAlbumFromLibrary(librarySelected.value, newAlbumName.value.trim())
    ElMessage.success(`相册「${result.album_name}」已创建，共 ${result.added} 张照片`)
    emit('imported', { type: 'album', album_id: result.album_id })
    librarySelected.value = []
    newAlbumName.value = ''
    visible.value = false
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '创建失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="导入"
    width="680px"
    :close-on-click-modal="!loading"
    class="imp-dialog"
  >
    <el-tabs v-model="activeTab" class="imp-tabs">

      <!-- ── Tab 1: Upload photos ── -->
      <el-tab-pane v-if="!props.hideTabs?.includes('photos')" label="上传照片" name="photos">
        <div class="imp-section">

          <!-- Drop zone — v-model:file-list handles additions; no @change needed -->
          <el-upload
            v-model:file-list="photoFiles"
            multiple
            :auto-upload="false"
            :show-file-list="false"
            accept=".jpg,.jpeg,.png,.heic,.heif,.webp,.bmp,.gif,.tiff"
            drag
            class="imp-dropzone"
          >
            <div class="imp-drop-inner">
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
                <rect x="3" y="3" width="18" height="18" rx="2"/>
                <circle cx="8.5" cy="8.5" r="1.5"/>
                <polyline points="21 15 16 10 5 21"/>
              </svg>
              <p>拖拽照片到这里，或 <em>点击选择</em></p>
              <small>支持 JPG / PNG / HEIC / WebP / BMP（最多 200 张）</small>
            </div>
          </el-upload>

          <!-- File list preview -->
          <div v-if="photoFiles.length" class="imp-file-list">
            <div class="imp-file-list-header">
              <span>已选 {{ photoFiles.length }} 张</span>
              <el-button text size="small" @click="photoFiles = []">清空</el-button>
            </div>
            <div class="imp-file-chips">
              <span v-for="f in photoFiles.slice(0, 20)" :key="f.uid" class="imp-chip">
                {{ f.name }}
                <button class="imp-chip-del" @click.stop="photoFiles = photoFiles.filter(x => x.uid !== f.uid)">×</button>
              </span>
              <span v-if="photoFiles.length > 20" class="imp-chip imp-chip--more">
                +{{ photoFiles.length - 20 }} 张…
              </span>
            </div>
          </div>

          <!-- Destination -->
          <el-form label-position="top">
            <el-form-item>
              <template #label>
                目标子目录
                <small class="imp-path-hint">{{ photoDestPath }}</small>
              </template>
              <el-input v-model="photoSubdir" placeholder="imported" clearable>
                <template #prepend>PicJournal /</template>
              </el-input>
            </el-form-item>
          </el-form>

          <!-- Progress -->
          <el-progress
            v-if="loading"
            :percentage="uploadPct"
            :striped="true"
            :striped-flow="true"
            status="success"
          />

          <!-- Result -->
          <el-alert
            v-if="photoResult"
            type="success"
            :closable="false"
          >
            已保存 {{ photoResult.saved }} 张，扫描任务 #{{ photoResult.scan_task_id }} 运行中
            <span v-if="photoResult.skipped.length">（跳过 {{ photoResult.skipped.length }} 个不支持文件）</span>
          </el-alert>

          <el-button
            type="primary"
            :loading="loading"
            :disabled="!photoFiles.length"
            style="width: 100%"
            @click="doImportPhotos"
          >
            开始导入
          </el-button>
        </div>
      </el-tab-pane>

      <!-- ── Tab 2: ZIP album ── -->
      <el-tab-pane label="ZIP 相册包" name="zip">
        <div class="imp-section">

          <el-upload
            v-model:file-list="zipFileList"
            :auto-upload="false"
            :limit="1"
            accept=".zip"
            drag
            class="imp-dropzone"
            @change="handleZipChange"
          >
            <div class="imp-drop-inner">
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
                <path d="M21 10H3M16 2v4M8 2v4M3 6h18v16H3z"/>
              </svg>
              <p>拖拽 ZIP 文件到这里，或 <em>点击选择</em></p>
              <small>支持标准 ZIP 和 Apple Photos 导出包（.photoslibrary 需先压缩为 ZIP）</small>
            </div>
          </el-upload>

          <!-- Album name is auto-filled from ZIP filename (no user input needed) -->
          <el-form label-position="top">
            <el-form-item v-if="!props.albumId">
              <template #label>
                目标子目录
                <small class="imp-path-hint">
                  {{ scanRoot ? `${scanRoot}/PicJournal/${zipSubdir || zipAlbumName || '…'}/` : '（需先运行扫描）' }}
                </small>
              </template>
              <el-input v-model="zipSubdir" :placeholder="zipAlbumName || 'album'" clearable>
                <template #prepend>PicJournal /</template>
              </el-input>
            </el-form-item>
          </el-form>

          <el-progress
            v-if="loading"
            :percentage="uploadPct"
            :striped="true"
            :striped-flow="true"
            status="success"
          />

          <el-button
            type="primary"
            :loading="loading"
            :disabled="!zipFile"
            style="width: 100%"
            @click="doImportZip"
          >
            {{ props.albumId ? '导入 ZIP 到当前相册' : '解压并建相册' }}
          </el-button>
        </div>
      </el-tab-pane>

      <!-- ── Tab 3: From library ── -->
      <el-tab-pane v-if="!props.hideTabs?.includes('library')" label="从库中选照片" name="library">
        <div class="imp-section">

          <div class="imp-lib-header">
            <span>已选 <strong>{{ librarySelected.length }}</strong> 张</span>
            <el-input
              v-model="newAlbumName"
              placeholder="新相册名称"
              style="max-width: 200px"
              clearable
            />
          </div>

          <!-- Photo grid -->
          <div v-if="libraryLoading" class="imp-lib-skeleton">
            <el-skeleton-item v-for="i in 12" :key="i" variant="image" class="imp-sk-item" />
          </div>

          <div v-else class="imp-lib-grid">
            <div
              v-for="photo in libraryPhotos"
              :key="photo.id"
              class="imp-lib-item"
              :class="{ selected: librarySelected.includes(photo.id) }"
              @click="toggleSelect(photo.id)"
            >
              <img
                v-if="photo.thumbnail_256"
                :src="photo.thumbnail_256"
                :alt="photo.ai_caption ?? ''"
                loading="lazy"
              />
              <div v-else class="imp-lib-item--empty" />
              <!-- Checkbox overlay -->
              <div class="imp-lib-check">
                <svg v-if="librarySelected.includes(photo.id)"
                     width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                </svg>
              </div>
            </div>
          </div>

          <!-- Pagination -->
          <el-pagination
            v-if="libraryTotal > 60"
            v-model:current-page="libraryPage"
            :page-size="60"
            :total="libraryTotal"
            layout="prev, pager, next"
            small
            class="imp-pagination"
          />

          <el-button
            type="primary"
            :loading="loading"
            :disabled="!librarySelected.length || !newAlbumName.trim()"
            style="width: 100%"
            @click="doImportFromLibrary"
          >
            创建相册（{{ librarySelected.length }} 张）
          </el-button>
        </div>
      </el-tab-pane>
    </el-tabs>
  </el-dialog>
</template>

<style scoped>
.imp-tabs { width: 100%; }

.imp-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px 0;
}

/* Drop zone */
.imp-dropzone { width: 100%; }

.imp-drop-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px;
  color: var(--no-text-secondary);

  p { margin: 0; font-size: 14px; em { font-style: normal; color: var(--el-color-primary); } }
  small { font-size: 11px; color: var(--no-text-muted); }
  svg { color: var(--no-text-muted); }
}

/* File list */
.imp-file-list { background: var(--no-bg-elevated); border-radius: 8px; padding: 10px 12px; }
.imp-file-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--no-text-secondary);
  margin-bottom: 8px;
}
.imp-file-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.imp-chip {
  font-size: 11px;
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  border-radius: 4px;
  padding: 2px 7px;
  color: var(--no-text-primary);
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.imp-chip--more { color: var(--no-text-muted); }
.imp-chip-del {
  margin-left: 4px;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--no-text-muted);
  font-size: 12px;
  line-height: 1;
  padding: 0 1px;
  vertical-align: middle;
  &:hover { color: var(--no-text-primary); }
}

/* Path hint */
.imp-path-hint {
  display: block;
  font-size: 10px;
  color: var(--no-text-muted);
  font-family: monospace;
  margin-top: 2px;
  font-weight: 400;
}

/* Library grid */
.imp-lib-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: var(--no-text-secondary);
}

.imp-lib-skeleton {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 4px;
}
.imp-sk-item { aspect-ratio: 1; border-radius: 6px; }

.imp-lib-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 4px;
  max-height: 340px;
  overflow-y: auto;
}

.imp-lib-item {
  position: relative;
  aspect-ratio: 1;
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
  transition: border-color 0.15s;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  &.selected { border-color: var(--el-color-primary); }
}

.imp-lib-item--empty {
  width: 100%;
  height: 100%;
  background: var(--no-bg-elevated);
}

.imp-lib-check {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--el-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  opacity: 0;
  transition: opacity 0.15s;

  .imp-lib-item.selected & { opacity: 1; }
}

.imp-pagination { justify-content: center; }

/* Mobile */
@media (max-width: 640px) {
  .imp-lib-grid { grid-template-columns: repeat(4, 1fr); }
  .imp-lib-skeleton { grid-template-columns: repeat(4, 1fr); }
}
</style>
