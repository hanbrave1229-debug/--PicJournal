<template>
  <div class="sa-page">
    <!-- Header -->
    <div class="sa-header">
      <div class="sa-header-left">
        <h1 class="sa-title">智能条件相册</h1>
        <p class="sa-subtitle">设定规则自动匹配照片，零物理空间冗余。</p>
      </div>
      <el-button class="sa-create-btn" @click="openRuleBuilder">
        <el-icon><Plus /></el-icon>
        创建智能规则
      </el-button>
    </div>

    <!-- Album cards grid -->
    <div v-if="!loading && albums.length === 0" class="sa-empty">
      <el-icon size="48" class="sa-empty-icon"><MagicStick /></el-icon>
      <p class="sa-empty-title">尚无智能相册</p>
      <p class="sa-empty-desc">创建条件规则后，系统将自动匹配满足条件的历史与未来照片。</p>
    </div>

    <div v-else class="sa-grid" v-loading="loading">
      <div
        v-for="album in albums"
        :key="album.id"
        class="sa-card"
      >
        <!-- Accent glow -->
        <div class="sa-card-glow" />

        <!-- Title + badge -->
        <div class="sa-card-head">
          <h2 class="sa-card-title">{{ album.title }}</h2>
          <span class="sa-card-badge">Smart AI</span>
        </div>

        <!-- Rules display -->
        <div class="sa-card-rules">
          <template v-if="parsedRules(album)">
            <div v-if="parsedRules(album)?.camera_model" class="sa-rule-row">
              <span class="sa-rule-key">设备</span>
              <span class="sa-rule-val">{{ parsedRules(album)?.camera_model }}</span>
            </div>
            <div v-if="parsedRules(album)?.quality_score_gt != null" class="sa-rule-row">
              <span class="sa-rule-key">质量分</span>
              <span class="sa-rule-val sa-rule-accent">≥ {{ parsedRules(album)?.quality_score_gt }}</span>
            </div>
            <div v-if="parsedRules(album)?.date_after" class="sa-rule-row">
              <span class="sa-rule-key">开始日期</span>
              <span class="sa-rule-val">{{ parsedRules(album)?.date_after }}</span>
            </div>
            <div v-if="parsedRules(album)?.date_before" class="sa-rule-row">
              <span class="sa-rule-key">结束日期</span>
              <span class="sa-rule-val">{{ parsedRules(album)?.date_before }}</span>
            </div>
            <div v-if="parsedRules(album)?.province || parsedRules(album)?.city" class="sa-rule-row">
              <span class="sa-rule-key">地理</span>
              <span class="sa-rule-val">
                {{ [parsedRules(album)?.province, parsedRules(album)?.city].filter(Boolean).join('·') }}
              </span>
            </div>
            <div v-if="!hasAnyRule(album)" class="sa-rule-none">无过滤条件（匹配所有照片）</div>
          </template>
          <div v-else class="sa-rule-none">无规则</div>
        </div>

        <!-- Evaluate result preview -->
        <div v-if="evalResults[album.id] !== undefined" class="sa-eval-result">
          <span class="sa-eval-count">{{ evalResults[album.id] }}</span>
          <span class="sa-eval-label">张匹配</span>
        </div>

        <!-- Actions -->
        <div class="sa-card-actions">
          <el-button
            size="small"
            plain
            class="sa-eval-btn"
            :loading="evaluatingId === album.id"
            @click="evaluateAlbum(album)"
          >
            动态查询
          </el-button>
          <el-button
            size="small"
            type="danger"
            plain
            @click="deleteAlbum(album)"
          >
            删除
          </el-button>
        </div>
      </div>
    </div>

    <!-- Rule builder dialog -->
    <el-dialog
      v-model="ruleBuilderVisible"
      title="创建智能条件相册"
      width="480px"
      class="sa-dialog"
      destroy-on-close
    >
      <el-form
        :model="newAlbum"
        label-position="top"
        label-width="auto"
        class="sa-form"
      >
        <el-form-item label="相册标题" required>
          <el-input
            v-model="newAlbum.title"
            placeholder="如：iPhone 人像精选"
            clearable
          />
        </el-form-item>

        <el-form-item label="筛选相机型号 (EXIF camera_model)">
          <el-input
            v-model="newAlbum.rules.camera_model"
            placeholder="如：iPhone 15、Sony A7"
            clearable
          />
        </el-form-item>

        <el-form-item label="AI 质量综合评分下限 (清晰度分)">
          <div class="sa-slider-wrap">
            <el-slider
              v-model="newAlbum.rules.quality_score_gt"
              :min="0"
              :max="500"
              :step="10"
              show-stops
              class="sa-slider"
            />
            <span class="sa-slider-val">≥ {{ newAlbum.rules.quality_score_gt }}</span>
          </div>
        </el-form-item>

        <div class="sa-form-row">
          <el-form-item label="拍摄日期 — 起始" style="flex:1">
            <el-date-picker
              v-model="newAlbum.rules.date_after"
              type="date"
              placeholder="不限"
              value-format="YYYY-MM-DD"
              style="width:100%"
            />
          </el-form-item>
          <el-form-item label="拍摄日期 — 截止" style="flex:1">
            <el-date-picker
              v-model="newAlbum.rules.date_before"
              type="date"
              placeholder="不限"
              value-format="YYYY-MM-DD"
              style="width:100%"
            />
          </el-form-item>
        </div>

        <div class="sa-form-row">
          <el-form-item label="省份" style="flex:1">
            <el-input v-model="newAlbum.rules.province" placeholder="如：浙江省" clearable />
          </el-form-item>
          <el-form-item label="城市" style="flex:1">
            <el-input v-model="newAlbum.rules.city" placeholder="如：杭州市" clearable />
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <div class="sa-dialog-footer">
          <el-button plain @click="ruleBuilderVisible = false">取消</el-button>
          <el-button
            class="sa-save-btn"
            :loading="saving"
            :disabled="!newAlbum.title.trim()"
            @click="saveSmartAlbum"
          >
            固化 SQL 动态规则
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, MagicStick } from '@element-plus/icons-vue'
import { albumsApi } from '@/api/albums'
import type { Album, SmartAlbumRules } from '@/types/album'

// ── State ──────────────────────────────────────────────────────────────────
const albums       = ref<Album[]>([])
const loading      = ref(false)
const saving       = ref(false)
const evaluatingId = ref<number | null>(null)
const evalResults  = ref<Record<number, number>>({})

const ruleBuilderVisible = ref(false)

interface NewAlbumForm {
  title: string
  rules: {
    camera_model: string
    quality_score_gt: number
    date_after: string
    date_before: string
    province: string
    city: string
  }
}

const defaultForm = (): NewAlbumForm => ({
  title: '',
  rules: {
    camera_model: '',
    quality_score_gt: 0,
    date_after: '',
    date_before: '',
    province: '',
    city: '',
  },
})

const newAlbum = ref<NewAlbumForm>(defaultForm())

// ── Load ────────────────────────────────────────────────────────────────────
async function loadAlbums(): Promise<void> {
  loading.value = true
  try {
    const { data } = await albumsApi.listSmart()
    albums.value = data.items
  } catch {
    ElMessage.error('加载智能相册失败')
  } finally {
    loading.value = false
  }
}

// ── Helpers ─────────────────────────────────────────────────────────────────
function parsedRules(album: Album): SmartAlbumRules | null {
  if (!album.smart_rules) return null
  try {
    return JSON.parse(album.smart_rules) as SmartAlbumRules
  } catch {
    return null
  }
}

function hasAnyRule(album: Album): boolean {
  const r = parsedRules(album)
  if (!r) return false
  return !!(r.camera_model || r.quality_score_gt || r.date_after || r.date_before || r.province || r.city)
}

// ── Rule builder ────────────────────────────────────────────────────────────
function openRuleBuilder(): void {
  newAlbum.value = defaultForm()
  ruleBuilderVisible.value = true
}

async function saveSmartAlbum(): Promise<void> {
  if (!newAlbum.value.title.trim()) return
  saving.value = true
  try {
    // Build rules object, stripping empty/zero values
    const r = newAlbum.value.rules
    const rules: SmartAlbumRules = {}
    if (r.camera_model.trim())    rules.camera_model = r.camera_model.trim()
    if (r.quality_score_gt > 0)   rules.quality_score_gt = r.quality_score_gt
    if (r.date_after)             rules.date_after = r.date_after
    if (r.date_before)            rules.date_before = r.date_before
    if (r.province.trim())        rules.province = r.province.trim()
    if (r.city.trim())            rules.city = r.city.trim()

    const { data: album } = await albumsApi.createSmart({
      title: newAlbum.value.title.trim(),
      is_smart: true,
      smart_rules: rules,
    })

    albums.value.unshift(album)
    ruleBuilderVisible.value = false
    ElMessage.success('规则已固化，SQLite 将动态匹配历史与未来照片')
  } catch {
    ElMessage.error('创建智能相册失败，请重试')
  } finally {
    saving.value = false
  }
}

// ── Evaluate ────────────────────────────────────────────────────────────────
async function evaluateAlbum(album: Album): Promise<void> {
  evaluatingId.value = album.id
  try {
    const { data } = await albumsApi.evaluate(album.id)
    evalResults.value[album.id] = data.total
    ElMessage.success(`「${album.title}」动态匹配 ${data.total} 张照片`)
  } catch {
    ElMessage.error('查询失败，请重试')
  } finally {
    evaluatingId.value = null
  }
}

// ── Delete ──────────────────────────────────────────────────────────────────
async function deleteAlbum(album: Album): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除智能相册「${album.title}」？`, '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await albumsApi.delete(album.id)
    albums.value = albums.value.filter(a => a.id !== album.id)
    ElMessage.success('已删除')
  } catch {
    ElMessage.error('删除失败')
  }
}

onMounted(loadAlbums)
</script>

<style lang="scss" scoped>
.sa-page { padding: 0; }

// ── Header ────────────────────────────────────────────────────────────────────
.sa-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 28px;
}

.sa-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--no-text-primary);
  margin: 0 0 6px;
}

.sa-subtitle {
  font-size: 13px;
  color: var(--no-text-muted);
  margin: 0;
}

.sa-create-btn {
  background: linear-gradient(135deg, #34d399 0%, #10b981 100%) !important;
  color: #0e0f11 !important;
  border: none !important;
  font-weight: 600;
}

// ── Empty state ───────────────────────────────────────────────────────────────
.sa-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 24px;
  border: 1px dashed var(--no-border-low);
  border-radius: 16px;
  text-align: center;
}

.sa-empty-icon {
  color: var(--no-accent);
  margin-bottom: 16px;
  opacity: 0.5;
}

.sa-empty-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--no-text-secondary);
  margin: 0 0 8px;
}

.sa-empty-desc {
  font-size: 13px;
  color: var(--no-text-muted);
  margin: 0;
  max-width: 400px;
  line-height: 1.6;
}

// ── Grid ──────────────────────────────────────────────────────────────────────
.sa-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  min-height: 100px;
}

// ── Card ──────────────────────────────────────────────────────────────────────
.sa-card {
  position: relative;
  overflow: hidden;
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  border-radius: 14px;
  padding: 20px;
  transition: background 200ms ease, transform 200ms ease, box-shadow 200ms ease;

  &:hover {
    background: #1e2126;
    transform: translateY(-2px);
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.5);

    .sa-card-glow {
      transform: scale(1.1);
    }
  }
}

.sa-card-glow {
  position: absolute;
  top: 0;
  right: 0;
  width: 80px;
  height: 80px;
  background: var(--no-accent);
  opacity: 0.05;
  border-bottom-left-radius: 100%;
  pointer-events: none;
  transition: transform 300ms ease;
}

.sa-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.sa-card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--no-text-primary);
  margin: 0;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sa-card-badge {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 4px;
  background: rgba(52, 211, 153, 0.1);
  color: var(--no-accent);
  border: 1px solid rgba(52, 211, 153, 0.2);
  white-space: nowrap;
  flex-shrink: 0;
  margin-left: 8px;
}

// ── Rules display ─────────────────────────────────────────────────────────────
.sa-card-rules {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
  min-height: 40px;
}

.sa-rule-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-family: var(--no-font-mono);
}

.sa-rule-key {
  width: 52px;
  color: var(--no-text-muted);
  flex-shrink: 0;
}

.sa-rule-val {
  color: var(--no-text-secondary);
}

.sa-rule-accent {
  color: var(--no-accent);
}

.sa-rule-none {
  font-size: 12px;
  color: var(--no-text-muted);
  font-style: italic;
}

// ── Eval result ───────────────────────────────────────────────────────────────
.sa-eval-result {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 12px;
  padding: 6px 10px;
  background: rgba(52, 211, 153, 0.06);
  border-radius: 6px;
  border: 1px solid rgba(52, 211, 153, 0.15);
}

.sa-eval-count {
  font-size: 20px;
  font-weight: 700;
  color: var(--no-accent);
  font-family: var(--no-font-mono);
}

.sa-eval-label {
  font-size: 12px;
  color: var(--no-text-muted);
}

// ── Card actions ──────────────────────────────────────────────────────────────
.sa-card-actions {
  display: flex;
  gap: 8px;
}

.sa-eval-btn {
  flex: 1;
}

// ── Dialog ────────────────────────────────────────────────────────────────────
:deep(.sa-dialog) {
  .el-dialog {
    background: #15171a;
    border: 1px solid #22252a;
    border-radius: 16px;
  }
  .el-dialog__title {
    color: var(--no-text-primary);
    font-weight: 600;
  }
  .el-dialog__header {
    border-bottom: 1px solid #22252a;
    margin-right: 0;
    padding-bottom: 16px;
  }
}

.sa-form {
  .el-form-item__label {
    font-size: 12px;
    color: var(--no-text-muted);
  }
}

.sa-form-row {
  display: flex;
  gap: 12px;
}

.sa-slider-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.sa-slider {
  flex: 1;
}

.sa-slider-val {
  font-size: 13px;
  font-family: var(--no-font-mono);
  color: var(--no-accent);
  white-space: nowrap;
  min-width: 48px;
  text-align: right;
}

.sa-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.sa-save-btn {
  background: linear-gradient(135deg, #34d399 0%, #10b981 100%) !important;
  color: #0e0f11 !important;
  border: none !important;
  font-weight: 600;
}
</style>
