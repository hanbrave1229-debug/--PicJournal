<template>
  <div class="al-root">
    <!-- Page header -->
    <div class="al-header">
      <div class="al-header-left">
        <h1>我的相册</h1>
        <p>将照片整理成专属相册，随时回顾珍贵记忆。</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新建相册</el-button>
    </div>

    <!-- Loading skeleton -->
    <div v-if="albumStore.loadingAlbums" class="al-grid">
      <div v-for="i in 6" :key="i" class="al-card al-card--skeleton" />
    </div>

    <!-- Album grid -->
    <div v-else-if="albumStore.albums.length" class="al-grid">
      <div
        v-for="album in albumStore.albums"
        :key="album.id"
        class="al-card"
        @click="goToAlbum(album.id)"
      >
        <!-- Cover -->
        <div class="al-card-cover">
          <img
            v-if="album.cover_thumbnail_url || album.cover_photo_id"
            :src="album.cover_thumbnail_url ?? `/api/v1/thumbnails/${album.cover_photo_id}?size=256`"
            class="al-cover-img"
            loading="lazy"
          />
          <div v-else class="al-cover-placeholder">
            <el-icon size="28"><Collection /></el-icon>
          </div>
          <!-- Hover actions -->
          <div class="al-card-actions" @click.stop>
            <el-button
              circle
              size="small"
              :icon="EditPen"
              class="al-action-btn"
              @click="openEdit(album)"
            />
            <el-button
              circle
              size="small"
              :icon="Delete"
              class="al-action-btn al-action-btn--danger"
              @click="confirmDelete(album)"
            />
          </div>
        </div>
        <!-- Info -->
        <div class="al-card-info">
          <span class="al-card-title">{{ album.title }}</span>
          <span class="al-card-count">{{ album.photo_count }} 张</span>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else class="al-empty">
      <div class="al-empty-icon">
        <el-icon size="40"><Collection /></el-icon>
      </div>
      <h2>还没有相册</h2>
      <p>创建相册，将照片归类整理。</p>
      <el-button type="primary" :icon="Plus" @click="openCreate">新建相册</el-button>
    </div>

    <!-- Create / Edit dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingAlbum ? '编辑相册' : '新建相册'"
      width="440px"
      destroy-on-close
    >
      <el-form :model="form" label-position="top" @submit.prevent="submitForm">
        <el-form-item label="相册名称" required>
          <el-input
            v-model="form.title"
            placeholder="例如：2024 旅行"
            maxlength="64"
            show-word-limit
            autofocus
          />
        </el-form-item>
        <el-form-item label="描述（可选）">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="为相册添加一段描述..."
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">
          {{ editingAlbum ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Collection, Delete, EditPen, Plus } from '@element-plus/icons-vue'
import { useAlbumStore } from '@/stores/useAlbumStore'
import type { Album } from '@/types/album'

const router = useRouter()
const albumStore = useAlbumStore()

// ── Form state ─────────────────────────────────────────────────────────────────
const dialogVisible = ref(false)
const editingAlbum = ref<Album | null>(null)
const submitting = ref(false)
const form = reactive({ title: '', description: '' })

// ── Lifecycle ──────────────────────────────────────────────────────────────────
onMounted(() => albumStore.fetchAlbums())

// ── Navigation ─────────────────────────────────────────────────────────────────
function goToAlbum(id: number) {
  router.push(`/albums/${id}`)
}

// ── Dialog helpers ─────────────────────────────────────────────────────────────
function openCreate() {
  editingAlbum.value = null
  form.title = ''
  form.description = ''
  dialogVisible.value = true
}

function openEdit(album: Album) {
  editingAlbum.value = album
  form.title = album.title
  form.description = album.description ?? ''
  dialogVisible.value = true
}

async function submitForm() {
  if (!form.title.trim()) {
    ElMessage.warning('请输入相册名称')
    return
  }
  submitting.value = true
  try {
    if (editingAlbum.value) {
      await albumStore.updateAlbum(editingAlbum.value.id, {
        title: form.title.trim(),
        description: form.description.trim() || undefined,
      })
      ElMessage.success('已更新')
    } else {
      await albumStore.createAlbum(form.title.trim(), form.description.trim() || undefined)
      ElMessage.success('相册已创建')
    }
    dialogVisible.value = false
  } finally {
    submitting.value = false
  }
}

// ── Delete ─────────────────────────────────────────────────────────────────────
async function confirmDelete(album: Album) {
  await ElMessageBox.confirm(
    `删除相册「${album.title}」后，相册内的照片不会被删除，只会移除归类关系。`,
    '确认删除',
    { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
  )
  await albumStore.deleteAlbum(album.id)
  ElMessage.success('相册已删除')
}
</script>

<style scoped lang="scss">
.al-root {
  min-height: 100%;
  color: var(--no-text-primary);
  font-family: var(--no-font-sans);
}

// ── Header ────────────────────────────────────────────────────────────────────
.al-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 28px;

  h1 { font-size: 22px; font-weight: 600; letter-spacing: -0.02em; margin: 0 0 4px; }
  p  { font-size: 13px; color: var(--no-text-secondary); margin: 0; }
}

// ── Grid ──────────────────────────────────────────────────────────────────────
.al-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}

// ── Card ──────────────────────────────────────────────────────────────────────
.al-card {
  border-radius: 10px;
  overflow: hidden;
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  cursor: pointer;
  transition: border-color 0.2s, transform 0.2s;

  &:hover {
    border-color: rgba(52, 211, 153, 0.35);
    transform: translateY(-2px);

    .al-card-actions { opacity: 1; }
  }

  &--skeleton {
    height: 210px;
    cursor: default;
    background: var(--no-bg-card-hover);
    animation: al-pulse 1.4s ease-in-out infinite;
  }
}

@keyframes al-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.4; }
}

// ── Cover ─────────────────────────────────────────────────────────────────────
.al-card-cover {
  position: relative;
  aspect-ratio: 1 / 1;
  background: var(--no-bg-card-hover);
  overflow: hidden;
}

.al-cover-img {
  width: 100%; height: 100%;
  object-fit: cover;
  display: block;
}

.al-cover-placeholder {
  width: 100%; height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--no-text-muted);
}

// ── Hover actions ─────────────────────────────────────────────────────────────
.al-card-actions {
  position: absolute;
  top: 8px; right: 8px;
  display: flex; gap: 6px;
  opacity: 0;
  transition: opacity 0.2s;
}

.al-action-btn {
  background: rgba(0, 0, 0, 0.55) !important;
  border: none !important;
  color: #fff !important;

  &--danger:hover {
    background: rgba(248, 113, 113, 0.75) !important;
  }
}

// ── Info ──────────────────────────────────────────────────────────────────────
.al-card-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  gap: 8px;
}

.al-card-title {
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.al-card-count {
  font-size: 11px;
  color: var(--no-text-muted);
  font-family: var(--no-font-mono);
  white-space: nowrap;
  flex-shrink: 0;
}

// ── Empty ─────────────────────────────────────────────────────────────────────
.al-empty {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 80px 20px; gap: 12px;
  text-align: center;

  h2 { font-size: 16px; font-weight: 500; margin: 0; }
  p  { font-size: 13px; color: var(--no-text-muted); margin: 0 0 8px; }
}

.al-empty-icon {
  width: 88px; height: 88px;
  border-radius: 50%;
  background: var(--no-bg-card-hover);
  display: flex; align-items: center; justify-content: center;
  color: var(--no-text-muted);
  margin-bottom: 8px;
}
</style>
