<template>
  <div class="bk">
    <header class="bk-header">
      <h1>手机备份</h1>
      <p class="bk-sub">选择手机里的照片/视频，自动跳过已备份的，只上传新增。</p>
    </header>

    <!-- File picker -->
    <label class="bk-pick" :class="{ 'is-busy': busy }">
      <input
        ref="inputRef"
        type="file"
        accept="image/*,video/*"
        multiple
        :disabled="busy"
        @change="onPick"
      />
      <el-icon size="34"><UploadFilled /></el-icon>
      <span class="bk-pick-title">{{ busy ? '处理中…' : '选择照片 / 视频' }}</span>
      <span class="bk-pick-hint">可一次多选；大相册建议分几次</span>
    </label>

    <!-- Progress -->
    <div v-if="phase !== 'idle'" class="bk-progress">
      <div class="bk-stage">{{ stageLabel }}</div>
      <el-progress
        :percentage="pct"
        :status="phase === 'done' ? 'success' : undefined"
        :stroke-width="14"
      />
      <div class="bk-counter" v-if="phase === 'hashing'">
        计算指纹 {{ hashedCount }} / {{ totalCount }}
      </div>
      <div class="bk-counter" v-else-if="phase === 'uploading'">
        上传 {{ uploadedCount }} / {{ toUploadCount }}
      </div>
    </div>

    <!-- Summary -->
    <div v-if="phase === 'done'" class="bk-summary">
      <div class="bk-stat bk-stat--new">
        <span class="bk-stat-num">{{ result.uploaded }}</span><span>新增上传</span>
      </div>
      <div class="bk-stat bk-stat--dup">
        <span class="bk-stat-num">{{ result.skipped }}</span><span>已备份跳过</span>
      </div>
      <div class="bk-stat bk-stat--bad" v-if="result.invalid > 0">
        <span class="bk-stat-num">{{ result.invalid }}</span><span>不支持/失败</span>
      </div>
    </div>

    <p v-if="phase === 'done'" class="bk-done-tip">
      上传的照片正在后台入库（生成缩略图、提取信息），稍后在时间轴可见。
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { backupApi } from '@/api/backup'
import { md5File } from '@/utils/md5'

type Phase = 'idle' | 'hashing' | 'checking' | 'uploading' | 'done'

const UPLOAD_BATCH = 15 // files per /backup/upload request

const inputRef = ref<HTMLInputElement | null>(null)
const phase = ref<Phase>('idle')
const busy = computed(() => phase.value !== 'idle' && phase.value !== 'done')

const totalCount = ref(0)
const hashedCount = ref(0)
const toUploadCount = ref(0)
const uploadedCount = ref(0)

const result = ref({ uploaded: 0, skipped: 0, invalid: 0 })

const pct = computed(() => {
  if (phase.value === 'hashing') {
    return totalCount.value ? Math.round((hashedCount.value / totalCount.value) * 100) : 0
  }
  if (phase.value === 'uploading') {
    return toUploadCount.value ? Math.round((uploadedCount.value / toUploadCount.value) * 100) : 0
  }
  if (phase.value === 'checking') return 100
  return phase.value === 'done' ? 100 : 0
})

const stageLabel = computed(() => ({
  hashing: '① 计算文件指纹（本地，不上传）',
  checking: '② 查询服务器已备份的照片',
  uploading: '③ 上传新增照片',
  done: '✓ 完成',
  idle: '',
}[phase.value]))

async function onPick(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  if (!files.length) return

  result.value = { uploaded: 0, skipped: 0, invalid: 0 }
  totalCount.value = files.length
  hashedCount.value = 0

  try {
    // ── 1. Hash all files locally ──────────────────────────────────────────
    phase.value = 'hashing'
    const hashes = new Map<string, File>() // md5 → file (dedup within selection too)
    for (const f of files) {
      try {
        const h = await md5File(f)
        if (!hashes.has(h)) hashes.set(h, f)
      } catch {
        result.value.invalid += 1
      }
      hashedCount.value += 1
    }

    // ── 2. Ask server which already exist ──────────────────────────────────
    phase.value = 'checking'
    const allHashes = [...hashes.keys()]
    const { data } = await backupApi.check(allHashes)
    const existing = new Set(data.existing)
    const missing = allHashes.filter((h) => !existing.has(h))
    result.value.skipped = allHashes.length - missing.length

    const toUpload = missing.map((h) => hashes.get(h)!).filter(Boolean)
    toUploadCount.value = toUpload.length
    uploadedCount.value = 0

    if (toUpload.length === 0) {
      phase.value = 'done'
      ElMessage.success('全部已备份，无需上传')
      return
    }

    // ── 3. Upload missing in batches ───────────────────────────────────────
    phase.value = 'uploading'
    for (let i = 0; i < toUpload.length; i += UPLOAD_BATCH) {
      const batch = toUpload.slice(i, i + UPLOAD_BATCH)
      const { data: up } = await backupApi.upload(batch)
      result.value.uploaded += up.saved
      result.value.skipped += up.skipped_duplicate
      result.value.invalid += up.skipped_invalid.length
      uploadedCount.value += batch.length
    }

    phase.value = 'done'
    ElMessage.success(`备份完成：新增 ${result.value.uploaded} 张`)
  } catch (err: any) {
    phase.value = 'idle'
    ElMessage.error(err?.response?.data?.detail ?? '备份失败，请重试')
  } finally {
    if (inputRef.value) inputRef.value.value = ''
  }
}
</script>

<style scoped>
.bk {
  max-width: 560px;
  margin: 0 auto;
  padding: 24px 16px 48px;
}
.bk-header h1 {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 6px;
}
.bk-sub {
  color: var(--no-text-low, #888);
  font-size: 14px;
  margin: 0 0 24px;
}
.bk-pick {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 16px;
  border: 2px dashed var(--no-border-low, #333);
  border-radius: 16px;
  color: var(--no-accent, #10b981);
  cursor: pointer;
  transition: border-color .2s, background .2s;
  text-align: center;
}
.bk-pick:hover { border-color: var(--no-accent, #10b981); background: rgba(16,185,129,.05); }
.bk-pick.is-busy { opacity: .6; pointer-events: none; }
.bk-pick input { display: none; }
.bk-pick-title { font-size: 16px; font-weight: 600; color: var(--no-text, #eee); }
.bk-pick-hint { font-size: 12px; color: var(--no-text-low, #888); }

.bk-progress { margin-top: 28px; }
.bk-stage { font-size: 14px; margin-bottom: 10px; color: var(--no-text, #ddd); }
.bk-counter { margin-top: 8px; font-size: 13px; color: var(--no-text-low, #888); }

.bk-summary { display: flex; gap: 12px; margin-top: 28px; }
.bk-stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 16px 8px;
  border-radius: 12px;
  background: var(--no-bg-card, #1a1a1a);
  font-size: 13px;
  color: var(--no-text-low, #999);
}
.bk-stat-num { font-size: 26px; font-weight: 700; color: var(--no-text, #eee); }
.bk-stat--new .bk-stat-num { color: #10b981; }
.bk-stat--dup .bk-stat-num { color: #3b82f6; }
.bk-stat--bad .bk-stat-num { color: #f59e0b; }

.bk-done-tip {
  margin-top: 20px;
  font-size: 13px;
  color: var(--no-text-low, #888);
  text-align: center;
}
</style>
