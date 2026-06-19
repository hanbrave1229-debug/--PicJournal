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

        <!-- ── 云端 AI 集成商（多配置） ──────────────────────────────── -->
        <div class="st-group">
          <div class="st-group-header">
            <div class="st-group-label">云端 AI 集成商</div>
            <el-button size="small" :icon="Plus" @click="openCfgDialog()">添加配置</el-button>
          </div>

          <!-- Config card list -->
          <div v-if="aiConfigs.length" class="st-ai-configs">
            <div
              v-for="cfg in aiConfigs"
              :key="cfg.id"
              class="st-ai-card"
              :class="{ 'st-ai-card--active': cfg.is_active }"
            >
              <!-- Active badge -->
              <span v-if="cfg.is_active" class="st-ai-badge">当前使用</span>

              <!-- Provider dot + name -->
              <div class="st-ai-card-header">
                <span
                  class="st-provider-dot"
                  :style="{ background: PROVIDERS.find(p => p.id === cfg.provider)?.color ?? '#888' }"
                />
                <span class="st-ai-card-name">{{ cfg.name }}</span>
                <span class="st-ai-card-provider">{{ PROVIDERS.find(p => p.id === cfg.provider)?.label ?? cfg.provider }}</span>
              </div>

              <!-- Meta -->
              <div class="st-ai-card-meta">
                <span class="st-ai-meta-item">
                  <span class="st-ai-meta-k">模型</span>
                  <span class="st-ai-meta-v">{{ cfg.model }}</span>
                </span>
                <span class="st-ai-meta-item">
                  <span class="st-ai-meta-k">Key</span>
                  <span
                    class="st-ai-meta-v st-ai-meta-key"
                    :class="{ 'st-key-warn': cfg.api_key_masked === '****' }"
                    :title="cfg.api_key_masked === '****' ? '密钥解密失败，请重新编辑填写' : ''"
                  >{{ cfg.api_key_masked || '未设置' }}{{ cfg.api_key_masked === '****' ? ' ⚠' : '' }}</span>
                </span>
                <span v-if="cfg.base_url" class="st-ai-meta-item">
                  <span class="st-ai-meta-k">URL</span>
                  <span class="st-ai-meta-v">{{ cfg.base_url }}</span>
                </span>
              </div>

              <!-- Actions -->
              <div class="st-ai-card-actions">
                <el-button
                  v-if="!cfg.is_active"
                  size="small"
                  type="primary"
                  plain
                  @click="activateConfig(cfg.id)"
                >设为当前</el-button>
                <el-button
                  size="small"
                  plain
                  :type="testingState[cfg.id] === 'ok' ? 'success' : testingState[cfg.id] === 'error' ? 'danger' : ''"
                  :loading="testingState[cfg.id] === 'testing'"
                  @click="testConfig(cfg.id)"
                >{{ testingState[cfg.id] === 'ok' ? '✓ 正常' : testingState[cfg.id] === 'error' ? '✗ 失败' : '测试' }}</el-button>
                <el-button size="small" plain @click="openCfgDialog(cfg)">编辑</el-button>
                <el-button
                  size="small"
                  plain
                  type="danger"
                  :disabled="cfg.is_active"
                  @click="deleteConfig(cfg)"
                >删除</el-button>
              </div>
            </div>
          </div>

          <!-- Empty state -->
          <div v-else class="st-ai-empty">
            <el-icon size="28"><Connection /></el-icon>
            <p>还没有 AI 配置，点击「添加配置」开始接入</p>
          </div>
        </div>

        <!-- Add / Edit dialog -->
        <el-dialog
          v-model="cfgDialogVisible"
          :title="editingCfg ? '编辑配置' : '添加 AI 配置'"
          width="480px"
          destroy-on-close
        >
          <el-form :model="cfgForm" label-position="top">
            <el-form-item label="配置名称">
              <el-input v-model="cfgForm.name" placeholder="例如：本地 Qwen VL、OpenAI GPT-4o" />
            </el-form-item>
            <el-form-item label="集成商">
              <el-select v-model="cfgForm.provider" style="width:100%" @change="onProviderChange">
                <el-option v-for="p in PROVIDERS" :key="p.id" :value="p.id" :label="p.label">
                  <div class="st-provider-option">
                    <span class="st-provider-option-dot" :style="{ background: p.color }" />
                    <span>{{ p.label }}</span>
                    <span class="st-provider-option-domain">{{ p.domain }}</span>
                  </div>
                </el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="API Key">
              <el-input
                v-model="cfgForm.api_key"
                :type="cfgShowKey ? 'text' : 'password'"
                :placeholder="editingCfg ? '留空则保持原 Key 不变' : 'sk-...'"
                clearable
              >
                <template #suffix>
                  <el-icon style="cursor:pointer" @click="cfgShowKey = !cfgShowKey">
                    <View v-if="!cfgShowKey" /><Hide v-else />
                  </el-icon>
                </template>
              </el-input>
              <div v-if="editingCfg?.api_key_masked" class="st-key-hint" :class="{ 'st-key-hint-warn': editingCfg.api_key_masked === '****' }">
                <template v-if="editingCfg.api_key_masked === '****'">
                  ⚠ 密钥解密失败（容器重启后丢失），请重新填写
                </template>
                <template v-else>
                  当前：{{ editingCfg.api_key_masked }}（留空则保持原 Key 不变）
                </template>
              </div>
            </el-form-item>
            <el-form-item label="Base URL">
              <el-input
                v-model="cfgForm.base_url"
                placeholder="http://192.168.3.x:1234/v1（留空使用集成商默认）"
                clearable
              />
            </el-form-item>
            <el-form-item label="模型">
              <el-input
                v-model="cfgForm.model"
                :placeholder="PROVIDERS.find(p=>p.id===cfgForm.provider)?.models[0]?.value ?? '例如 gpt-4o'"
                clearable
              />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="cfgDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="cfgSaving" @click="saveCfgDialog">
              {{ editingCfg ? '保存' : '创建' }}
            </el-button>
          </template>
        </el-dialog>

        <!-- ── AI 批量打标 ─────────────────────────────────────────── -->
        <div class="st-section-divider">VLM 多模态批量打标</div>

        <!-- Stats overview -->
        <div v-if="photoStats" class="st-stats-bar">
          <div class="st-stat-item">
            <span class="st-stat-val">{{ photoStats.total }}</span>
            <span class="st-stat-label">总照片</span>
          </div>
          <div class="st-stat-sep" />
          <div class="st-stat-item st-stat-item--done">
            <span class="st-stat-val">{{ photoStats.tagged }}</span>
            <span class="st-stat-label">已打标</span>
          </div>
          <div class="st-stat-sep" />
          <div class="st-stat-item st-stat-item--pending">
            <span class="st-stat-val">{{ photoStats.untagged }}</span>
            <span class="st-stat-label">未打标</span>
          </div>
          <div class="st-stat-sep" />
          <div class="st-stat-item">
            <span class="st-stat-val">{{ photoStats.face_analyzed }}</span>
            <span class="st-stat-label">已识人脸</span>
          </div>
          <!-- Progress bar -->
          <div class="st-stats-progress">
            <div
              class="st-stats-progress-fill"
              :style="{ width: photoStats.total ? (photoStats.tagged / photoStats.total * 100).toFixed(1) + '%' : '0%' }"
            />
            <span class="st-stats-progress-pct">
              {{ photoStats.total ? (photoStats.tagged / photoStats.total * 100).toFixed(0) : 0 }}%
            </span>
          </div>
        </div>

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
                  :min="1" :max="1000"
                  size="small"
                  controls-position="right"
                  style="width: 80px"
                />
              </div>
              <div class="st-tag-limit-wrap">
                <span class="st-tag-limit-label">并发数</span>
                <el-input-number
                  v-model="ai.vlmConcurrency"
                  :min="1" :max="8"
                  size="small"
                  controls-position="right"
                  style="width: 70px"
                  @change="saveAiConfig"
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
              <div v-if="tagStatus.last_failure && !tagStatus.running" class="st-tag-failure-detail">
                {{ tagStatus.last_failure }}
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

          <!-- 文字识别（未开发） -->
          <div class="st-row st-row--tall st-row--disabled">
            <div class="st-row-info">
              <div class="st-row-title">
                文字识别 (OCR)
                <el-tag size="small" type="info" effect="plain" round>未开发</el-tag>
              </div>
              <div class="st-row-desc">自动识别照片内的文字内容</div>
            </div>
            <el-switch v-model="ai.ocr" disabled />
          </div>

          <!-- 相似重复 -->
          <div class="st-row st-row--tall">
            <div class="st-row-info">
              <div class="st-row-title">相似 / 重复照片识别</div>
              <div class="st-row-desc">识别相似或重复的照片并归类</div>
            </div>
            <el-switch v-model="ai.duplicates" />
          </div>

          <!-- 宠物识别（未开发） -->
          <div class="st-row st-row--tall st-row--disabled">
            <div class="st-row-info">
              <div class="st-row-title">
                宠物识别
                <el-tag size="small" type="info" effect="plain" round>未开发</el-tag>
              </div>
              <div class="st-row-desc">支持 39 种猫狗品种识别</div>
            </div>
            <div class="st-row-controls">
              <el-button size="small" plain disabled>重新识别</el-button>
              <el-switch v-model="ai.pets" disabled />
            </div>
          </div>

          <!-- 画面识别（未开发） -->
          <div class="st-row st-row--tall st-row--last st-row--disabled">
            <div class="st-row-info">
              <div class="st-row-title">
                画面识别
                <el-tag size="small" type="info" effect="plain" round>未开发</el-tag>
              </div>
              <div class="st-row-desc">图片内容理解，包含以文搜图、场景物体识别等功能</div>
            </div>
            <div class="st-row-controls">
              <el-button size="small" plain disabled>重新识别</el-button>
              <el-switch v-model="ai.scene" disabled />
            </div>
          </div>

        </div>

        <div class="st-section-divider">XMP 元数据同步</div>

        <div class="st-card">
          <!-- Export DB → XMP -->
          <div class="st-row st-row--tall">
            <div class="st-row-info">
              <div class="st-row-title">导出标签到 XMP</div>
              <div class="st-row-desc">将 AI 生成的描述和标签写回照片旁的 .xmp 文件（兼容 Lightroom / digiKam）</div>
            </div>
            <el-button
              size="small"
              :loading="xmpExporting"
              @click="xmpExport"
            >导出</el-button>
          </div>

          <!-- Import XMP → DB -->
          <div class="st-row st-row--tall">
            <div class="st-row-info">
              <div class="st-row-title">从 XMP 导入（以文件为准）</div>
              <div class="st-row-desc">当 .xmp 文件比数据库记录更新时，用 XMP 覆盖 DB（适用于外部软件编辑后同步）</div>
            </div>
            <el-button
              size="small"
              :loading="xmpImporting"
              @click="xmpImport"
            >导入</el-button>
          </div>

          <!-- Conflict list -->
          <div class="st-row st-row--tall st-row--last">
            <div class="st-row-info">
              <div class="st-row-title">查看冲突</div>
              <div class="st-row-desc">列出 XMP 与数据库内容不一致的照片</div>
            </div>
            <el-button size="small" plain @click="xmpShowConflicts">查看冲突</el-button>
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

        <!-- 定时扫描 -->
        <div class="st-group">
          <div class="st-group-label">定时扫描</div>
          <div class="st-card st-card--flat">
            <div class="st-autoscan-row">
              <div class="st-autoscan-text">
                <div class="st-autoscan-title">自动发现新增照片/视频</div>
                <div class="st-autoscan-desc">
                  周期性扫描最近扫描的目录（增量，已入库的会跳过）。关闭则仅手动扫描。
                </div>
              </div>
              <el-switch v-model="autoScan.enabled" />
            </div>
            <div v-if="autoScan.enabled" class="st-autoscan-interval">
              <span>扫描间隔</span>
              <el-input-number
                v-model="autoScan.intervalMinutes"
                :min="5"
                :max="1440"
                :step="5"
                controls-position="right"
              />
              <span>分钟</span>
            </div>
            <div class="st-autoscan-actions">
              <el-button type="primary" :loading="autoScanSaving" @click="saveAutoScan">
                保存
              </el-button>
            </div>
          </div>
        </div>

        <!-- 语义索引（向量搜索） -->
        <div class="st-group">
          <div class="st-group-label">语义索引（向量搜索）</div>
          <div class="st-card st-card--flat">
            <div class="st-autoscan-row">
              <div class="st-autoscan-text">
                <div class="st-autoscan-title">CLIP 向量嵌入</div>
                <div class="st-autoscan-desc">
                  为照片生成语义向量后，「向量搜索」才能用自然语言搜图（如「夕阳」「笑脸」）。
                  CPU 密集，建议空闲时跑。已嵌入的会跳过。
                </div>
              </div>
            </div>
            <div class="st-embed-status">
              <span :class="['st-embed-dot', clipStatus.available ? 'is-on' : 'is-off']" />
              <span>模型：{{ clipStatus.available ? '就绪' : '不可用' }}</span>
              <span class="st-embed-sep">·</span>
              <span>已嵌入 {{ clipStatus.embedded_photos }} / {{ clipStatus.total_photos }}</span>
            </div>
            <el-progress
              v-if="clipStatus.total_photos > 0"
              :percentage="embedPct"
              :stroke-width="12"
              :status="embedPct === 100 ? 'success' : undefined"
            />
            <div class="st-autoscan-actions">
              <el-button
                type="primary"
                :loading="embedStarting"
                :disabled="!clipStatus.available || embedRunning"
                @click="startEmbedding"
              >
                {{ embedRunning ? '嵌入中…' : '开始嵌入' }}
              </el-button>
              <el-button text :disabled="embedRunning" @click="refreshClipStatus">刷新状态</el-button>
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

        <!-- 导入历史 -->
        <div class="st-group">
          <div class="st-group-label">导入历史</div>
          <div class="st-card st-card--flat">
            <div v-if="!importHistory.length" class="st-import-empty">暂无导入记录</div>
            <el-table v-else :data="importHistory" size="small" class="st-table">
              <el-table-column prop="scan_path" label="导入路径" min-width="180" show-overflow-tooltip />
              <el-table-column label="状态" width="80">
                <template #default="{ row }">
                  <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="文件数" width="90">
                <template #default="{ row }">{{ row.processed_files }} / {{ row.total_files }}</template>
              </el-table-column>
              <el-table-column label="时间" width="150">
                <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
              </el-table-column>
            </el-table>
          </div>
        </div>

      </div>
    </Transition>

    <!-- ── 账号安全 ────────────────────────────────────────────────────── -->
    <Transition name="st-fade">
      <div v-if="activeTab === 'account'" class="st-panel">
        <div class="st-account-card">
          <div class="st-account-head">
            <div>
              <div class="st-account-name">{{ auth.user?.username || '当前账号' }}</div>
              <div class="st-account-role">{{ auth.user?.role === 'admin' ? '管理员' : '普通用户' }}</div>
            </div>
            <el-button @click="onLogout">退出登录</el-button>
          </div>

          <h3 class="st-account-subtitle">修改密码</h3>
          <el-form label-position="top" class="st-account-form">
            <el-form-item label="原密码">
              <el-input v-model="pwdForm.old" type="password" show-password placeholder="请输入原密码" />
            </el-form-item>
            <el-form-item label="新密码">
              <el-input v-model="pwdForm.new1" type="password" show-password placeholder="至少 6 位" />
            </el-form-item>
            <el-form-item label="确认新密码">
              <el-input v-model="pwdForm.new2" type="password" show-password placeholder="再次输入新密码" />
            </el-form-item>
            <el-button type="primary" :loading="pwdSaving" @click="onChangePassword">保存新密码</el-button>
          </el-form>
        </div>
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
import { computed, reactive, ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowDown, CircleCloseFilled, Connection, Folder, FolderOpened,
  Hide, Plus, Share, SuccessFilled, UserFilled, View,
} from '@element-plus/icons-vue'
import { useScanStore } from '@/stores/useScanStore'
import { useScanWebSocket } from '@/composables/useScanWebSocket'
import ScanProgress from '@/components/common/ScanProgress.vue'
import { formatDate } from '@/utils/format'
import axios from 'axios'
import { configApi } from '@/api/config'
import { searchApi } from '@/api/search'
import { PROVIDERS } from '@/types/config'
import type { AIProvider, ConnectionTestResponse } from '@/types/config'
import { useRouter } from 'vue-router'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/useAuthStore'

// ── 账号安全 ───────────────────────────────────────────────────────────────────
const router = useRouter()
const auth = useAuthStore()
const pwdForm = reactive({ old: '', new1: '', new2: '' })
const pwdSaving = ref(false)

onMounted(() => {
  if (!auth.user) auth.fetchMe().catch(() => {})
})

async function onChangePassword() {
  if (!pwdForm.old || !pwdForm.new1) {
    ElMessage.warning('请填写原密码和新密码')
    return
  }
  if (pwdForm.new1.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  if (pwdForm.new1 !== pwdForm.new2) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  pwdSaving.value = true
  try {
    await authApi.changePassword(pwdForm.old, pwdForm.new1)
    ElMessage.success('密码已修改')
    pwdForm.old = pwdForm.new1 = pwdForm.new2 = ''
  } catch {
    /* error toast handled by axios interceptor */
  } finally {
    pwdSaving.value = false
  }
}

async function onLogout() {
  await auth.logout()
  router.replace('/login')
}

// ── AI 多配置管理 ───────────────────────────────────────────────────────────────

interface AiModelConfig {
  id: number
  name: string
  provider: string
  api_key_masked: string
  base_url: string | null
  model: string
  is_active: boolean
}

const aiConfigs     = ref<AiModelConfig[]>([])
const cfgDialogVisible = ref(false)
const editingCfg    = ref<AiModelConfig | null>(null)
const cfgShowKey    = ref(false)
const cfgSaving     = ref(false)
const cfgForm       = reactive({
  name:     '',
  provider: 'custom' as AIProvider,
  api_key:  '',
  base_url: '',
  model:    '',
})

async function loadAiConfigs() {
  try {
    const { data } = await axios.get<AiModelConfig[]>('/api/v1/ai-configs')
    aiConfigs.value = data
  } catch { /* ignore */ }
}

function openCfgDialog(cfg?: AiModelConfig) {
  editingCfg.value  = cfg ?? null
  cfgShowKey.value  = false
  cfgForm.name      = cfg?.name     ?? ''
  cfgForm.provider  = (cfg?.provider ?? 'custom') as AIProvider
  cfgForm.api_key   = ''            // never pre-fill key
  cfgForm.base_url  = cfg?.base_url ?? ''
  cfgForm.model     = cfg?.model    ?? ''
  cfgDialogVisible.value = true
}

function onProviderChange() {
  const p = PROVIDERS.find(p => p.id === cfgForm.provider)
  if (p) cfgForm.model = p.models[0]?.value ?? ''
}

/**
 * Encrypt a plaintext API key with the server's ephemeral RSA-OAEP public key.
 * Returns base64 ciphertext. Falls back to plaintext if WebCrypto is unavailable.
 */
async function encryptApiKey(plaintext: string): Promise<Record<string, string>> {
  if (!plaintext) return {}  // no key field → backend keeps existing encrypted key
  try {
    const { data } = await axios.get<{ pubkey: string }>('/api/v1/ai-configs/pubkey')
    const spkiDer = Uint8Array.from(atob(data.pubkey), c => c.charCodeAt(0))
    const pubKey = await crypto.subtle.importKey(
      'spki', spkiDer,
      { name: 'RSA-OAEP', hash: 'SHA-256' },
      false, ['encrypt'],
    )
    const cipherBuf = await crypto.subtle.encrypt(
      { name: 'RSA-OAEP' }, pubKey,
      new TextEncoder().encode(plaintext),
    )
    const cipherB64 = btoa(String.fromCharCode(...new Uint8Array(cipherBuf)))
    return { api_key_cipher: cipherB64 }
  } catch {
    // fallback: plaintext (e.g. HTTP context where SubtleCrypto is restricted)
    return { api_key: plaintext }
  }
}

async function saveCfgDialog() {
  if (!cfgForm.name.trim() || !cfgForm.model.trim()) {
    ElMessage.warning('请填写配置名称和模型名称')
    return
  }
  cfgSaving.value = true
  try {
    const keyPayload = await encryptApiKey(cfgForm.api_key)

    if (editingCfg.value) {
      await axios.put(`/api/v1/ai-configs/${editingCfg.value.id}`, {
        name:     cfgForm.name.trim(),
        provider: cfgForm.provider,
        ...keyPayload,
        base_url: cfgForm.base_url.trim() || null,
        model:    cfgForm.model.trim(),
      })
      ElMessage.success('配置已更新')
    } else {
      await axios.post('/api/v1/ai-configs', {
        name:     cfgForm.name.trim(),
        provider: cfgForm.provider,
        ...keyPayload,
        base_url: cfgForm.base_url.trim() || null,
        model:    cfgForm.model.trim(),
      })
      ElMessage.success('配置已创建')
    }
    cfgDialogVisible.value = false
    await loadAiConfigs()
  } finally {
    cfgSaving.value = false
  }
}

// key: configId → 'testing' | 'ok' | 'error' | null
const testingState = ref<Record<number, 'testing' | 'ok' | 'error' | null>>({})

async function testConfig(id: number) {
  testingState.value[id] = 'testing'
  try {
    const { data } = await axios.post(`/api/v1/ai-configs/${id}/test`)
    if (data.ok) {
      testingState.value[id] = 'ok'
      ElMessage.success(`连通正常，延迟 ${data.latency_ms} ms`)
    } else {
      testingState.value[id] = 'error'
      ElMessage.error(data.error || '请求失败')
    }
  } catch {
    testingState.value[id] = 'error'
    ElMessage.error('测试请求异常')
  } finally {
    setTimeout(() => { testingState.value[id] = null }, 4000)
  }
}

async function activateConfig(id: number) {
  await axios.post(`/api/v1/ai-configs/${id}/activate`)
  await loadAiConfigs()
  ElMessage.success('已切换为当前模型')
}

async function deleteConfig(cfg: AiModelConfig) {
  await ElMessageBox.confirm(
    `删除配置「${cfg.name}」？此操作不可撤销。`,
    '确认删除',
    { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
  )
  await axios.delete(`/api/v1/ai-configs/${cfg.id}`)
  await loadAiConfigs()
  ElMessage.success('已删除')
}

// ── Tabs ───────────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'general',  name: '通用设置' },
  { id: 'ai',       name: '智能设置' },
  { id: 'folders',  name: '文件夹范围' },
  { id: 'account',  name: '账号安全' },
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
  vlmConcurrency: 1,
})

// ── 定时扫描 state ──────────────────────────────────────────────────────────────
const autoScan = reactive({
  enabled: true,
  intervalMinutes: 30,
})
const autoScanSaving = ref(false)

async function saveAutoScan() {
  autoScanSaving.value = true
  try {
    await configApi.update({
      auto_scan_enabled: autoScan.enabled,
      auto_scan_interval_minutes: autoScan.intervalMinutes,
    })
    toast('定时扫描设置已保存')
  } finally {
    autoScanSaving.value = false
  }
}

// ── 语义索引（CLIP 向量嵌入）─────────────────────────────────────────────────
const clipStatus = reactive({
  available: false,
  total_photos: 0,
  embedded_photos: 0,
  index_size: 0,
})
const embedStarting = ref(false)
let embedPollTimer: ReturnType<typeof setInterval> | null = null

const embedPct = computed(() =>
  clipStatus.total_photos > 0
    ? Math.round((clipStatus.embedded_photos / clipStatus.total_photos) * 100)
    : 0,
)
const embedRunning = computed(() =>
  clipStatus.total_photos > 0 && clipStatus.embedded_photos < clipStatus.total_photos && embedPollTimer !== null,
)

async function refreshClipStatus() {
  try {
    const { data } = await searchApi.semanticStatus()
    clipStatus.available = data.available
    clipStatus.total_photos = data.total_photos
    clipStatus.embedded_photos = data.embedded_photos
    clipStatus.index_size = data.index_size
  } catch { /* ignore */ }
}

async function startEmbedding() {
  embedStarting.value = true
  try {
    await searchApi.startEmbedding(false)
    toast('已开始嵌入，后台进行中')
    // Poll status until fully embedded
    if (embedPollTimer) clearInterval(embedPollTimer)
    embedPollTimer = setInterval(async () => {
      await refreshClipStatus()
      if (clipStatus.embedded_photos >= clipStatus.total_photos) {
        if (embedPollTimer) clearInterval(embedPollTimer)
        embedPollTimer = null
        toast('嵌入完成，向量搜索已就绪')
      }
    }, 5000)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail ?? '启动嵌入失败')
  } finally {
    embedStarting.value = false
  }
}

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

// ── Import history ────────────────────────────────────────────────────────────
const importHistory = ref<any[]>([])
async function loadImportHistory() {
  try {
    const { data } = await axios.get('/api/v1/import/history', { params: { page: 1, page_size: 20 } })
    importHistory.value = data.items
  } catch { /* ignore */ }
}

onMounted(() => {
  scanStore.fetchTasks()
  loadAiConfigs()
  loadPhotoStats()
  loadImportHistory()
  refreshClipStatus()
  // Restore progress if a tagging task was running before page reload
  pollTagStatus().then(() => {
    if (tagRunning.value && !tagPollTimer) {
      tagPollTimer = setInterval(pollTagStatus, 1500)
    }
  })
})

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
    ai.peopleMinCount  = data.face_min_photos ?? 5
    ai.vlmConcurrency  = data.vlm_concurrency ?? 1
    autoScan.enabled         = data.auto_scan_enabled ?? true
    autoScan.intervalMinutes = data.auto_scan_interval_minutes ?? 30
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
      ai_auto_tag:     aiCfg.autoTag,
      ai_batch_size:   aiCfg.batchSize,
      face_min_photos: ai.peopleMinCount,
      vlm_concurrency: ai.vlmConcurrency,
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

onUnmounted(() => {
  if (tagPollTimer) {
    clearInterval(tagPollTimer)
    tagPollTimer = null
  }
  if (embedPollTimer) {
    clearInterval(embedPollTimer)
    embedPollTimer = null
  }
})

// ── AI Batch Tagging ──────────────────────────────────────────────────────────

interface TagStatus {
  running: boolean
  total: number
  done: number
  failed: number
  percent: number
  current_file: string
  error: string | null
  last_failure: string | null
}

// ── Photo stats ───────────────────────────────────────────────────────────────
interface PhotoStats {
  total: number; tagged: number; untagged: number
  videos: number; photos: number; duplicates: number; face_analyzed: number
}
const photoStats = ref<PhotoStats | null>(null)
async function loadPhotoStats() {
  try {
    const { data } = await axios.get<PhotoStats>('/api/v1/photos/stats')
    photoStats.value = data
  } catch { /* ignore */ }
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
        if (data.failed > 0 && data.done === 0) {
          const hint = data.last_failure ? `\n原因：${data.last_failure}` : ''
          ElMessage.error({ message: `打标全部失败（${data.failed} 张）${hint}`, duration: 8000 })
        } else if (data.failed > 0) {
          const hint = data.last_failure ? `，最近失败原因：${data.last_failure}` : ''
          ElMessage.warning({ message: `打标完成：成功 ${data.done} 张，失败 ${data.failed} 张${hint}`, duration: 6000 })
        } else {
          ElMessage.success(`打标完成：成功 ${data.done} 张`)
        }
        loadPhotoStats()  // refresh coverage stats
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

// ── XMP Sync ──────────────────────────────────────────────────────────────────

const xmpExporting = ref(false)
const xmpImporting = ref(false)

async function xmpExport() {
  xmpExporting.value = true
  try {
    const { data } = await axios.post('/api/v1/xmp-sync/export')
    ElMessage.success(`XMP 导出完成：更新 ${data.updated} 个文件，跳过 ${data.skipped}，失败 ${data.errors}`)
  } catch {
    ElMessage.error('XMP 导出失败')
  } finally {
    xmpExporting.value = false
  }
}

async function xmpImport() {
  xmpImporting.value = true
  try {
    const { data } = await axios.post('/api/v1/xmp-sync/import')
    ElMessage.success(`XMP 导入完成：更新 ${data.updated} 条记录，跳过 ${data.skipped}，失败 ${data.errors}`)
  } catch {
    ElMessage.error('XMP 导入失败')
  } finally {
    xmpImporting.value = false
  }
}

async function xmpShowConflicts() {
  try {
    const { data } = await axios.get<Array<{
      photo_id: number; file_path: string
      db_caption: string | null; xmp_caption: string | null
      db_tags: string[]; xmp_tags: string[]
    }>>('/api/v1/xmp-sync/conflicts')
    if (data.length === 0) {
      ElMessage.success('没有冲突，DB 与 XMP 完全一致')
    } else {
      const lines = data.slice(0, 10).map(c =>
        `• ${c.file_path.split('/').pop()}\n  DB: ${c.db_caption ?? '(空)'} → XMP: ${c.xmp_caption ?? '(空)'}`
      ).join('\n')
      ElMessageBox.alert(
        `共 ${data.length} 个冲突（显示前 10 条）:\n\n${lines}`,
        'XMP 冲突列表',
        { confirmButtonText: '知道了', customStyle: { whiteSpace: 'pre-wrap' } }
      )
    }
  } catch {
    ElMessage.error('获取冲突列表失败')
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

.st-import-empty {
  font-size: 13px;
  color: var(--no-text-muted);
  padding: 16px;
  text-align: center;
}

.st-group-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--no-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 8px;
}

.st-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;

  .st-group-label { margin-bottom: 0; }
}

// ── AI 多配置卡片 ─────────────────────────────────────────────────────────────

.st-ai-configs {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.st-ai-card {
  border: 1px solid var(--no-border-low);
  border-radius: 10px;
  padding: 14px 16px;
  background: var(--no-bg-card);
  position: relative;
  transition: border-color 0.2s;

  &--active {
    border-color: rgba(52, 211, 153, 0.5);
    background: rgba(52, 211, 153, 0.04);
  }
}

.st-ai-badge {
  position: absolute;
  top: 10px;
  right: 12px;
  font-size: 11px;
  font-weight: 500;
  color: #10b981;
  background: rgba(16, 185, 129, 0.12);
  padding: 2px 8px;
  border-radius: 20px;
}

.st-ai-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.st-provider-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.st-ai-card-name {
  font-size: 14px;
  font-weight: 500;
}

.st-ai-card-provider {
  font-size: 12px;
  color: var(--no-text-muted);
}

.st-ai-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
}

.st-ai-meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.st-ai-meta-k {
  color: var(--no-text-muted);
}

.st-ai-meta-v {
  color: var(--no-text-secondary);

  &.st-ai-meta-key {
    font-family: var(--no-font-mono);
    letter-spacing: 0.02em;
  }
  &.st-key-warn {
    color: var(--el-color-warning);
  }
}

.st-ai-card-actions {
  display: flex;
  gap: 8px;
}

.st-ai-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 32px 0;
  color: var(--no-text-muted);
  font-size: 13px;
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
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 未开发功能：整行置灰 */
.st-row--disabled {
  opacity: 0.55;
}
.st-row--disabled .st-row-title {
  color: var(--no-text-secondary);
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

// ── Photo stats bar ──────────────────────────────────────────────────────────
.st-stats-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  border-radius: 10px;
  padding: 14px 18px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.st-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 52px;
  .st-stat-val {
    font-size: 22px;
    font-weight: 700;
    line-height: 1.1;
    color: var(--no-text-primary);
  }
  .st-stat-label {
    font-size: 10px;
    color: var(--no-text-muted);
    margin-top: 2px;
    white-space: nowrap;
  }
  &.st-stat-item--done .st-stat-val { color: #10b981; }
  &.st-stat-item--pending .st-stat-val { color: var(--no-text-secondary); }
}
.st-stat-sep {
  width: 1px;
  height: 32px;
  background: var(--no-border-low);
}
.st-stats-progress {
  flex: 1;
  min-width: 100px;
  position: relative;
  height: 6px;
  background: var(--no-bg-elevated);
  border-radius: 3px;
  overflow: hidden;
  .st-stats-progress-fill {
    height: 100%;
    background: #10b981;
    border-radius: 3px;
    transition: width 0.4s ease;
  }
  .st-stats-progress-pct {
    position: absolute;
    right: 0;
    top: -18px;
    font-size: 11px;
    color: var(--no-text-muted);
  }
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

.st-tag-failure-detail {
  margin-top: 4px;
  font-size: 11px;
  color: #f87171;
  font-family: var(--no-font-mono);
  word-break: break-all;
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
  &.st-key-hint-warn {
    color: var(--el-color-warning);
    font-family: inherit;
  }
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

// ── 账号安全 ───────────────────────────────────────────────────────────────────
.st-account-card {
  max-width: 460px;
  background: var(--no-bg-card);
  border: 1px solid var(--no-border-low);
  border-radius: 12px;
  padding: 24px;
}
.st-account-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 18px;
  margin-bottom: 18px;
  border-bottom: 1px solid var(--no-border-low);
}
.st-account-name { font-size: 16px; font-weight: 600; color: var(--no-text-primary); }
.st-account-role { font-size: 12px; color: var(--no-text-muted); margin-top: 2px; }
.st-account-subtitle { font-size: 14px; font-weight: 600; margin: 0 0 14px; color: var(--no-text-primary); }
.st-account-form { display: flex; flex-direction: column; }

// ── 定时扫描 ───────────────────────────────────────────────────────────────────
.st-autoscan-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.st-autoscan-title { font-size: 14px; font-weight: 500; color: var(--no-text-primary); }
.st-autoscan-desc { font-size: 12px; color: var(--no-text-muted); margin-top: 4px; max-width: 520px; }
.st-autoscan-interval {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  font-size: 13px;
  color: var(--no-text-secondary);
}
.st-autoscan-actions { margin-top: 16px; }
</style>
