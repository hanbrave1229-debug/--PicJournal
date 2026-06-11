<template>
  <div class="st-root">
    <!-- Page title -->
    <div class="st-page-header">
      <h1>系统设置</h1>
      <p>管理扫描目录、智能识别与显示偏好。</p>
    </div>

    <!-- Tab nav -->
    <div class="st-tabs">
      <div
        v-for="tab in TABS"
        :key="tab.id"
        :class="['st-tab', activeTab === tab.id && 'is-active']"
        @click="activeTab = tab.id"
      >
        {{ tab.name }}
        <span v-if="activeTab === tab.id" class="st-tab-bar" />
      </div>
    </div>

    <!-- ── 通用设置 ────────────────────────────────────────────────────── -->
    <Transition name="st-fade">
      <div v-if="activeTab === 'general'" class="st-panel st-panel--general">

        <div class="st-group">
          <div class="st-group-label">图片显示</div>
          <div class="st-card">
            <div class="st-row">
              <span>图片比例</span>
              <el-radio-group v-model="general.aspectRatio" size="small">
                <el-radio value="square">方形</el-radio>
                <el-radio value="original">原始比例</el-radio>
              </el-radio-group>
            </div>
            <div class="st-row">
              <span>显示照片来源信息</span>
              <el-switch v-model="general.showSource" />
            </div>
          </div>
        </div>

        <div class="st-group">
          <div class="st-group-label">重复项目设置</div>
          <div class="st-card">
            <div class="st-row">
              <span>上传 / 移动 / 复制时</span>
              <el-select v-model="general.duplicateAction" size="small" style="width:120px">
                <el-option label="覆盖" value="overwrite" />
                <el-option label="跳过" value="skip" />
                <el-option label="保留两者" value="keep_both" />
              </el-select>
            </div>
          </div>
        </div>

        <div class="st-group">
          <div class="st-group-label">其他设置</div>
          <div class="st-card">
            <div class="st-row">
              <span>显示文件夹视图</span>
              <el-switch v-model="general.showFolderView" />
            </div>
            <div class="st-row">
              <span>允许普通用户共享照片</span>
              <el-switch v-model="general.allowShare" />
            </div>
          </div>
        </div>

      </div>
    </Transition>

    <!-- ── 智能设置 ────────────────────────────────────────────────────── -->
    <Transition name="st-fade">
      <div v-if="activeTab === 'ai'" class="st-panel">

        <!-- ── AI 集成商配置 ─────────────────────────────────────────── -->
        <div class="st-group">
          <div class="st-group-label">云端 AI 集成商</div>

          <!-- Provider dropdown -->
          <div class="st-ai-form">
            <div class="st-form-row">
              <label class="st-form-label">集成商</label>
              <el-select
                v-model="aiCfg.provider"
                placeholder="请选择集成商"
                style="width:100%"
                @change="selectProvider"
              >
                <el-option
                  v-for="p in PROVIDERS"
                  :key="p.id"
                  :value="p.id"
                  :label="p.label"
                >
                  <div class="st-provider-option">
                    <span class="st-provider-option-dot" :style="{ background: p.color }" />
                    <span>{{ p.label }}</span>
                    <span class="st-provider-option-domain">{{ p.domain }}</span>
                  </div>
                </el-option>
              </el-select>
            </div>

            <!-- API Key -->
            <div class="st-form-row">
              <label class="st-form-label">API Key</label>
              <div class="st-form-input-wrap">
                <el-input
                  v-model="aiCfg.apiKey"
                  :type="showKey ? 'text' : 'password'"
                  :placeholder="currentProvider?.keyPlaceholder ?? 'sk-...'"
                  clearable
                  class="st-key-input"
                >
                  <template #suffix>
                    <el-icon style="cursor:pointer" @click="showKey = !showKey">
                      <View v-if="!showKey" />
                      <Hide v-else />
                    </el-icon>
                  </template>
                </el-input>
                <div class="st-key-hint">{{ maskedKey || '密钥未设置' }}</div>
              </div>
            </div>

            <!-- Base URL (custom only) -->
            <div v-if="currentProvider?.baseUrlRequired" class="st-form-row">
              <label class="st-form-label">Base URL</label>
              <el-input
                v-model="aiCfg.baseUrl"
                placeholder="https://your-endpoint.com/v1"
                clearable
              />
            </div>

            <!-- Model input -->
            <div class="st-form-row">
              <label class="st-form-label">模型</label>
              <el-input
                v-model="aiCfg.model"
                :placeholder="currentProvider?.models[0]?.value ?? '例如 gpt-4o-mini'"
                clearable
              />
            </div>

            <!-- Behaviour toggles -->
            <div class="st-form-row st-form-row--inline">
              <label class="st-form-label">启用云端识别</label>
              <el-switch v-model="aiCfg.enabled" />
            </div>
            <div class="st-form-row st-form-row--inline">
              <label class="st-form-label">扫描后自动标注</label>
              <el-switch v-model="aiCfg.autoTag" />
            </div>
            <div class="st-form-row st-form-row--inline">
              <label class="st-form-label">批处理大小</label>
              <el-input-number
                v-model="aiCfg.batchSize"
                :min="1" :max="20"
                size="small"
                controls-position="right"
              />
            </div>

            <!-- Action row -->
            <div class="st-form-actions">
              <!-- Connection test result badge -->
              <div v-if="testResult" :class="['st-test-badge', testResult.ok ? 'is-ok' : 'is-err']">
                <el-icon><SuccessFilled v-if="testResult.ok" /><CircleCloseFilled v-else /></el-icon>
                <span>{{ testResult.message }}</span>
                <span v-if="testResult.latency_ms" class="st-test-ms">{{ testResult.latency_ms }} ms</span>
              </div>
              <div style="flex:1" />
              <el-button
                :loading="testing"
                plain
                size="small"
                @click="testConnection"
              >
                测试连接
              </el-button>
              <el-button
                type="primary"
                size="small"
                :loading="saving"
                @click="saveAiConfig"
              >
                保存配置
              </el-button>
            </div>

          </div>
        </div>

        <!-- ── AI 批量打标 ─────────────────────────────────────────── -->
        <div class="st-section-divider">VLM 多模态批量打标</div>

        <div class="st-card st-tag-panel">
          <div class="st-row st-row--tall">
            <div class="st-row-info">
              <div class="st-row-title">批量 AI 打标</div>
              <div class="st-row-desc">
                调用上方配置的 VLM 模型，为未打标照片生成中文描述与关键词标签，
                为「AI 日记主笔」和未来的自然语言搜索提供数据基础。
              </div>
            </div>
            <div class="st-row-controls">
              <div class="st-tag-limit-wrap">
                <span class="st-tag-limit-label">本次上限</span>
                <el-input-number
                  v-model="tagLimit"
                  :min="1" :max="500"
                  size="small"
                  controls-position="right"
                  style="width: 80px"
                />
              </div>
              <el-button
                type="primary"
                size="small"
                color="#6366f1"
                :loading="tagRunning"
                :disabled="tagRunning"
                @click="startTagging"
              >
                {{ tagRunning ? '打标中…' : '开始打标' }}
              </el-button>
            </div>
          </div>

          <!-- Progress bar (shown only when running or just finished) -->
          <Transition name="st-fade">
            <div v-if="tagStatus.total > 0" class="st-tag-progress-wrap">
              <el-progress
                :percentage="tagStatus.percent"
                :status="tagStatus.running ? '' : (tagStatus.failed > 0 ? 'warning' : 'success')"
                :stroke-width="6"
                striped
                :striped-flow="tagStatus.running"
              />
              <div class="st-tag-stats">
                <span>已完成 {{ tagStatus.done }} / {{ tagStatus.total }}</span>
                <span v-if="tagStatus.failed > 0" class="st-tag-failed">
                  失败 {{ tagStatus.failed }}
                </span>
                <span v-if="tagStatus.current_file" class="st-tag-current">
                  {{ tagStatus.current_file }}
                </span>
              </div>
            </div>
          </Transition>
        </div>

        <!-- Divider -->
        <div class="st-section-divider">识别功能开关</div>

        <div class="st-card">

          <!-- 人物识别 -->
          <div class="st-row st-row--tall">
            <div class="st-row-info">
              <div class="st-row-title">人物识别</div>
              <div class="st-row-desc">识别图片、视频中的人物并归类</div>
            </div>
            <div class="st-row-controls">
              <el-button size="small" plain @click="toast('正在重新建立面部特征库...')">重新识别</el-button>
              <el-switch v-model="ai.people" />
            </div>
          </div>
          <!-- Sub-options -->
          <div v-if="ai.people" class="st-sub-panel">
            <div class="st-sub-row">
              <span>形成人物相册的最少照片数</span>
              <el-input-number
                v-model="ai.peopleMinCount"
                :min="1" :max="20"
                size="small"
                controls-position="right"
              />
            </div>
            <div class="st-sub-row">
              <el-checkbox v-model="ai.peopleInVideo">识别视频中的人物</el-checkbox>
            </div>
          </div>

          <!-- 文字识别 -->
          <div class="st-row st-row--tall">
            <div class="st-row-info">
              <div class="st-row-title">文字识别 (OCR)</div>
              <div class="st-row-desc">自动识别照片内的文字内容</div>
            </div>
            <el-switch v-model="ai.ocr" />
          </div>

          <!-- 相似重复 -->
          <div class="st-row st-row--tall">
            <div class="st-row-info">
              <div class="st-row-title">相似 / 重复照片识别</div>
              <div class="st-row-desc">识别相似或重复的照片并归类</div>
            </div>
            <el-switch v-model="ai.duplicates" />
          </div>

          <!-- 宠物识别 -->
          <div class="st-row st-row--tall">
            <div class="st-row-info">
              <div class="st-row-title">宠物识别</div>
              <div class="st-row-desc">支持 39 种猫狗品种识别</div>
            </div>
            <div class="st-row-controls">
              <el-button size="small" plain @click="toast('正在重新扫描宠物特征...')">重新识别</el-button>
              <el-switch v-model="ai.pets" />
            </div>
          </div>

          <!-- 画面识别 -->
          <div class="st-row st-row--tall st-row--last">
            <div class="st-row-info">
              <div class="st-row-title">画面识别</div>
              <div class="st-row-desc">图片内容理解，包含以文搜图、场景物体识别等功能</div>
            </div>
            <div class="st-row-controls">
              <el-button size="small" plain @click="toast('场景物体识别模型初始化中...')">重新识别</el-button>
              <el-switch v-model="ai.scene" />
            </div>
          </div>

        </div>

      </div>
    </Transition>

    <!-- ── 文件夹范围 ──────────────────────────────────────────────────── -->
    <Transition name="st-fade">
      <div v-if="activeTab === 'folders'" class="st-panel">

        <!-- 扫描路径输入（保留原有功能） -->
        <div class="st-group">
          <div class="st-group-label">扫描目录</div>
          <div class="st-card st-card--flat">
            <div class="st-scan-row">
              <el-input
                v-model="newPath"
                placeholder="/photos"
                clearable
                class="st-path-input"
                @keyup.enter="startScan"
              >
                <template #prefix>
                  <el-icon><FolderOpened /></el-icon>
                </template>
              </el-input>
              <el-button type="primary" :loading="scanning" @click="startScan">
                开始扫描
              </el-button>
            </div>
          </div>
        </div>

        <!-- 个人文件夹列表 -->
        <div class="st-group">
          <div class="st-folder-header">
            <div class="st-folder-title">
              <el-icon class="st-folder-chevron"><ArrowDown /></el-icon>
              个人文件夹
            </div>
            <div class="st-folder-actions">
              <el-button size="small" plain @click="toast('正在全盘扫描新文件...')">扫描</el-button>
              <el-button size="small" plain @click="toast('请通过上方路径框添加目录')">＋</el-button>
            </div>
          </div>

          <div class="st-folder-table">
            <div class="st-ft-head">
              <div class="st-ft-col st-ft-col--name">文件夹</div>
              <div class="st-ft-col">路径</div>
            </div>
            <div
              v-for="row in folderRows"
              :key="row.path"
              class="st-ft-row"
            >
              <div class="st-ft-col st-ft-col--name">
                <el-icon class="st-folder-icon"><Folder /></el-icon>
                {{ row.name }}
                <span v-if="row.isDefault" class="st-badge-default">默认</span>
              </div>
              <div class="st-ft-col st-ft-muted">{{ row.path }}</div>
            </div>
          </div>
        </div>

        <!-- 扫描历史 -->
        <div class="st-group">
          <div class="st-group-label">扫描历史</div>
          <div class="st-card st-card--flat">
            <el-table
              :data="scanStore.tasks"
              size="small"
              class="st-table"
            >
              <el-table-column prop="scan_path" label="路径" min-width="200" show-overflow-tooltip />
              <el-table-column label="状态" width="90">
                <template #default="{ row }">
                  <el-tag :type="statusType(row.status)" size="small">
                    {{ statusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="进度" width="120">
                <template #default="{ row }">
                  <el-progress
                    :percentage="row.progress_pct"
                    :show-text="false"
                    :status="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'exception' : undefined"
                  />
                </template>
              </el-table-column>
              <el-table-column label="文件数" width="100">
                <template #default="{ row }">
                  {{ row.processed_files }} / {{ row.total_files }}
                </template>
              </el-table-column>
              <el-table-column prop="finished_at" label="完成时间" width="160">
                <template #default="{ row }">{{ formatDate(row.finished_at) }}</template>
              </el-table-column>
            </el-table>
          </div>
        </div>

        <!-- 活跃扫描进度 -->
        <ScanProgress v-if="scanStore.activeTask" :task="scanStore.activeTask" />

      </div>
    </Transition>

    <!-- ── 共享管理 ────────────────────────────────────────────────────── -->
    <Transition name="st-fade">
      <div v-if="activeTab === 'share'" class="st-panel st-coming-soon">
        <el-icon size="40" class="st-cs-icon"><Share /></el-icon>
        <h2>共享管理</h2>
        <p>该功能正在开发中，敬请期待。</p>
      </div>
    </Transition>

    <!-- ── 好友上传管理 ─────────────────────────────────────────────────── -->
    <Transition name="st-fade">
      <div v-if="activeTab === 'friends'" class="st-panel st-coming-soon">
        <el-icon size="40" class="st-cs-icon"><UserFilled /></el-icon>
        <h2>好友上传管理</h2>
        <p>该功能正在开发中，敬请期待。</p>
      </div>
    </Transition>

  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ArrowDown, CircleCloseFilled, Folder, FolderOpened,
  Hide, Share, SuccessFilled, UserFilled, View,
} from '@element-plus/icons-vue'
import { useScanStore } from '@/stores/useScanStore'
import { useScanWebSocket } from '@/composables/useScanWebSocket'
import ScanProgress from '@/components/common/ScanProgress.vue'
import { formatDate } from '@/utils/format'
import axios from 'axios'
import { configApi } from '@/api/config'
import { PROVIDERS } from '@/types/config'
import type { AIProvider, ConnectionTestResponse } from '@/types/config'

// ── Tabs ───────────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'general',  name: '通用设置' },
  { id: 'ai',       name: '智能设置' },
  { id: 'folders',  name: '文件夹范围' },
  { id: 'share',    name: '共享管理' },
  { id: 'friends',  name: '好友上传管理' },
] as const

type TabId = typeof TABS[number]['id']
const activeTab = ref<TabId>('general')

// ── 通用设置 state ──────────────────────────────────────────────────────────────
const general = reactive({
  aspectRatio: 'original' as 'square' | 'original',
  showSource: true,
  duplicateAction: 'overwrite' as 'overwrite' | 'skip' | 'keep_both',
  showFolderView: true,
  allowShare: true,
})

// ── 智能设置 state ──────────────────────────────────────────────────────────────
const ai = reactive({
  people: true,
  peopleMinCount: 5,
  peopleInVideo: true,
  ocr: false,
  duplicates: true,
  pets: true,
  scene: true,
})

// ── 文件夹 (static mock — real data comes from scan tasks) ─────────────────────
const folderRows = [
  { name: 'Photos',       path: '个人文件夹/Photos',       isDefault: true  },
  { name: 'MobileBackup', path: '个人文件夹/MobileBackup', isDefault: false },
]

// ── 扫描（保留原有功能）──────────────────────────────────────────────────────────
const scanStore = useScanStore()
const { connect } = useScanWebSocket()
const newPath = ref('/photos')
const scanning = ref(false)

onMounted(() => scanStore.fetchTasks())

async function startScan() {
  if (!newPath.value.trim()) return
  scanning.value = true
  try {
    const task = await scanStore.startScan(newPath.value.trim())
    connect(task.id)
    ElMessage.success(`扫描已启动，任务 ID: ${task.id}`)
  } finally {
    scanning.value = false
  }
}

function statusLabel(s: string) {
  return ({ pending: '等待', running: '扫描中', completed: '完成', failed: '失败' } as Record<string, string>)[s] ?? s
}

function statusType(s: string): '' | 'success' | 'info' | 'warning' | 'danger' {
  return ({ pending: 'info', running: '', completed: 'success', failed: 'danger' } as Record<string, '' | 'success' | 'info' | 'warning' | 'danger'>)[s] ?? 'info'
}

// ── Toast helper ───────────────────────────────────────────────────────────────
function toast(msg: string) {
  ElMessage({ message: msg, type: 'success', duration: 2000 })
}

// ── AI 集成商配置 ───────────────────────────────────────────────────────────────
const aiCfg = reactive({
  provider:  '' as AIProvider,
  apiKey:    '',           // '' = not changed; filled = user is setting a new key
  model:     '',
  baseUrl:   '' as string | null,
  enabled:   false,
  autoTag:   false,
  batchSize: 5,
})

/** Masked key fetched from server */
const maskedKey = ref('')
const showKey   = ref(false)
const saving    = ref(false)
const testing   = ref(false)
const testResult = ref<ConnectionTestResponse | null>(null)

const currentProvider = computed(() => PROVIDERS.find((p) => p.id === aiCfg.provider) ?? null)

async function loadAiConfig() {
  try {
    const { data } = await configApi.get()
    aiCfg.provider  = data.ai_provider
    aiCfg.model     = data.ai_model
    aiCfg.baseUrl   = data.ai_base_url
    aiCfg.enabled   = data.ai_enabled
    aiCfg.autoTag   = data.ai_auto_tag
    aiCfg.batchSize = data.ai_batch_size
    maskedKey.value = data.ai_api_key_masked
  } catch { /* ignore — backend may not be running */ }
}

function selectProvider(id: AIProvider) {
  aiCfg.provider  = id
  aiCfg.apiKey    = ''
  aiCfg.model     = currentProvider.value?.models[0]?.value ?? ''
  aiCfg.baseUrl   = null
  testResult.value = null
}

async function testConnection() {
  if (!aiCfg.provider) return
  testing.value = true
  testResult.value = null
  try {
    const { data } = await configApi.test({
      provider: aiCfg.provider,
      api_key:  aiCfg.apiKey || maskedKey.value, // fallback to masked (server resolves)
      model:    aiCfg.model,
      base_url: aiCfg.baseUrl,
    })
    testResult.value = data
  } finally {
    testing.value = false
  }
}

async function saveAiConfig() {
  saving.value = true
  try {
    const patch: Record<string, unknown> = {
      ai_provider:   aiCfg.provider,
      ai_model:      aiCfg.model,
      ai_base_url:   aiCfg.baseUrl || null,
      ai_enabled:    aiCfg.enabled,
      ai_auto_tag:   aiCfg.autoTag,
      ai_batch_size: aiCfg.batchSize,
    }
    // Only send key if the user explicitly typed one
    if (aiCfg.apiKey.trim()) {
      patch.ai_api_key = aiCfg.apiKey.trim()
    }
    const { data } = await configApi.update(patch)
    maskedKey.value = data.ai_api_key_masked
    aiCfg.apiKey = ''   // clear plaintext after save
    toast('配置已保存')
  } finally {
    saving.value = false
  }
}

onMounted(loadAiConfig)

// ── AI Batch Tagging ──────────────────────────────────────────────────────────

interface TagStatus {
  running: boolean
  total: number
  done: number
  failed: number
  percent: number
  current_file: string
  error: string | null
}

const tagLimit  = ref(50)
const tagRunning = ref(false)
const tagStatus  = ref<TagStatus>({
  running: false,
  total: 0,
  done: 0,
  failed: 0,
  percent: 0,
  current_file: '',
  error: null,
})

let tagPollTimer: ReturnType<typeof setInterval> | null = null

async function pollTagStatus(): Promise<void> {
  try {
    const { data } = await axios.get<TagStatus>('/api/v1/scan/tag-status')
    tagStatus.value = data
    tagRunning.value = data.running
    if (!data.running && tagPollTimer) {
      clearInterval(tagPollTimer)
      tagPollTimer = null
      if (data.error) {
        ElMessage.error(`打标任务出错: ${data.error}`)
      } else if (data.total > 0) {
        ElMessage.success(`打标完成：成功 ${data.done} 张，失败 ${data.failed} 张`)
      }
    }
  } catch {
    // ignore poll errors
  }
}

async function startTagging(): Promise<void> {
  if (tagRunning.value) return
  try {
    const { data } = await axios.post<{ started: boolean; reason?: string; total?: number }>(
      '/api/v1/scan/tag-photos',
      null,
      { params: { limit: tagLimit.value } }
    )
    if (!data.started) {
      ElMessage.warning(data.reason ?? '无法启动打标任务')
      return
    }
    tagRunning.value = true
    tagStatus.value = {
      running: true,
      total: data.total ?? 0,
      done: 0,
      failed: 0,
      percent: 0,
      current_file: '',
      error: null,
    }
    ElMessage.success(`已开始为 ${data.total} 张照片打标，请稍候…`)
    // Poll every 1.5s
    tagPollTimer = setInterval(pollTagStatus, 1500)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail ?? '启动打标失败，请检查 AI 配置')
  }
}
</script>

<style scoped lang="scss">
.st-root {
  max-width: 860px;
  font-family: var(--no-font-sans);
  color: var(--no-text-primary);
}

// ── Page header ───────────────────────────────────────────────────────────────
.st-page-header {
  margin-bottom: 28px;

  h1 { font-size: 22px; font-weight: 600; letter-spacing: -0.02em; margin: 0 0 4px; }
  p  { font-size: 13px; color: var(--no-text-secondary); margin: 0; }
}

// ── Tab nav ───────────────────────────────────────────────────────────────────
.st-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--no-border-low);
  margin-bottom: 28px;
}

.st-tab {
  position: relative;
  padding: 0 4px 14px;
  margin-right: 28px;
  font-size: 14px;
  color: var(--no-text-secondary);
  cursor: pointer;
  transition: color 0.15s;
  white-space: nowrap;

  &:hover { color: var(--no-text-primary); }

  &.is-active {
    color: var(--no-text-primary);
    font-weight: 500;
  }
}

.st-tab-bar {
  position: absolute;
  bottom: 0; left: 0;
  width: 100%; height: 2px;
  background: var(--no-accent);
  border-radius: 2px 2px 0 0;
}

// ── Panel ─────────────────────────────────────────────────────────────────────
.st-panel {
  max-width: 800px;

  &--general { }
}

// ── Group (section with label) ────────────────────────────────────────────────
.st-group {
  margin-bottom: 28px;
}

.st-group-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--no-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 8px;
}

// ── Card container ────────────────────────────────────────────────────────────
.st-card {
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  border-radius: 12px;
  overflow: hidden;

  &--flat {
    padding: 16px 20px;
  }
}

// ── Row (list item inside card) ───────────────────────────────────────────────
.st-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--no-border-low);
  font-size: 14px;
  gap: 16px;

  &:last-child,
  &--last { border-bottom: none; }

  &--tall { align-items: flex-start; padding: 18px 20px; }

  > span:first-child { color: var(--no-text-primary); }
}

.st-row-info {
  flex: 1;
}

.st-row-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--no-text-primary);
  margin-bottom: 3px;
}

.st-row-desc {
  font-size: 12px;
  color: var(--no-text-secondary);
}

.st-row-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

// ── AI sub-panel ──────────────────────────────────────────────────────────────
.st-sub-panel {
  margin: 0 20px 16px;
  background: var(--no-bg-card-hover);
  border: 1px solid var(--no-border-low);
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.st-sub-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: var(--no-text-primary);
}

// ── Scan row ──────────────────────────────────────────────────────────────────
.st-scan-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.st-path-input { flex: 1; }

// ── Folder section ────────────────────────────────────────────────────────────
.st-folder-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.st-folder-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
  color: var(--no-text-primary);
}

.st-folder-chevron { color: var(--no-text-muted); font-size: 12px; }

.st-folder-actions { display: flex; gap: 8px; }

.st-folder-table {
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  border-radius: 12px;
  overflow: hidden;
}

.st-ft-head {
  display: grid;
  grid-template-columns: 2fr 3fr;
  padding: 10px 16px;
  background: var(--no-bg-card-hover);
  border-bottom: 1px solid var(--no-border-low);
  font-size: 12px;
  color: var(--no-text-muted);
  font-weight: 500;
}

.st-ft-row {
  display: grid;
  grid-template-columns: 2fr 3fr;
  padding: 12px 16px;
  font-size: 13px;
  border-bottom: 1px solid var(--no-border-low);
  transition: background 0.12s;
  align-items: center;

  &:last-child { border-bottom: none; }
  &:hover { background: var(--no-bg-card-hover); }
}

.st-ft-col {
  display: flex;
  align-items: center;
  gap: 8px;

  &--name { font-weight: 500; color: var(--no-text-primary); }
}

.st-ft-muted { color: var(--no-text-secondary); font-family: var(--no-font-mono); font-size: 12px; }

.st-folder-icon { color: #60a5fa; font-size: 16px; }

.st-badge-default {
  padding: 1px 7px;
  font-size: 11px;
  background: rgba(96, 165, 250, 0.15);
  color: #60a5fa;
  border-radius: 4px;
  font-weight: 500;
}

// ── Table override ────────────────────────────────────────────────────────────
.st-table {
  background: transparent !important;

  :deep(.el-table__header-wrapper th) {
    background: var(--no-bg-card-hover) !important;
    color: var(--no-text-muted) !important;
    font-size: 12px;
  }

  :deep(.el-table__row td) {
    background: transparent !important;
    font-size: 12px;
    border-color: var(--no-border-low) !important;
  }
}

// ── Coming soon ───────────────────────────────────────────────────────────────
.st-coming-soon {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80px 20px;
  gap: 12px;
  text-align: center;
  color: var(--no-text-muted);

  h2 { font-size: 16px; font-weight: 500; margin: 0; color: var(--no-text-primary); }
  p  { font-size: 13px; margin: 0; }
}

.st-cs-icon {
  background: var(--no-bg-card-hover);
  padding: 20px;
  border-radius: 50%;
  margin-bottom: 4px;
}

// ── Section divider ───────────────────────────────────────────────────────────
.st-section-divider {
  font-size: 12px;
  font-weight: 500;
  color: var(--no-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0 0 16px;
  padding-top: 8px;
  border-top: 1px solid var(--no-border-low);
}

// ── AI Tagging panel ─────────────────────────────────────────────────────────
.st-tag-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.st-tag-limit-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--no-text-muted);
}

.st-tag-progress-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 2px;
}

.st-tag-stats {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--no-text-muted);
}

.st-tag-failed {
  color: #f87171;
}

.st-tag-current {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--no-font-mono);
  color: var(--no-text-secondary);
}

// ── Provider select option ────────────────────────────────────────────────────
.st-provider-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.st-provider-option-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.st-provider-option-domain {
  margin-left: auto;
  font-size: 11px;
  color: var(--no-text-muted);
  font-family: var(--no-font-mono);
}

// ── AI form ───────────────────────────────────────────────────────────────────
.st-ai-form {
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.st-form-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;

  &--inline { align-items: center; }
}

.st-form-label {
  width: 130px;
  flex-shrink: 0;
  font-size: 13px;
  color: var(--no-text-secondary);
  padding-top: 8px;

  .st-form-row--inline & { padding-top: 0; }
}

.st-form-input-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.st-key-input { width: 100%; }

.st-key-hint {
  font-size: 11px;
  color: var(--no-text-muted);
  font-family: var(--no-font-mono);
}

// ── Action row ────────────────────────────────────────────────────────────────
.st-form-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 4px;
  border-top: 1px solid var(--no-border-low);
}

.st-test-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 6px;

  &.is-ok  { background: rgba(52,211,153,0.1);  color: var(--no-accent); }
  &.is-err { background: rgba(248,113,113,0.1); color: #f87171; }
}

.st-test-ms {
  font-family: var(--no-font-mono);
  font-size: 11px;
  opacity: 0.7;
}

// ── Fade transition ───────────────────────────────────────────────────────────
.st-fade-enter-active { transition: opacity 0.2s ease, transform 0.2s ease; }
.st-fade-enter-from   { opacity: 0; transform: translateY(5px); }
</style>
