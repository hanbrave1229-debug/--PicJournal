<template>
  <el-card v-if="task" class="scan-progress" shadow="never">
    <div class="scan-header">
      <el-icon class="spin" v-if="task.status === 'running'"><Loading /></el-icon>
      <el-icon v-else-if="task.status === 'completed'" color="var(--el-color-success)"><CircleCheck /></el-icon>
      <el-icon v-else-if="task.status === 'failed'" color="var(--el-color-danger)"><CircleClose /></el-icon>
      <span class="scan-path">{{ task.scan_path }}</span>
      <el-tag size="small" :type="statusType">{{ statusLabel }}</el-tag>
    </div>

    <el-progress
      :percentage="task.progress_pct"
      :status="progressStatus"
      :striped="task.status === 'running'"
      :striped-flow="task.status === 'running'"
      :duration="10"
      class="scan-bar"
    />

    <div class="scan-meta">
      <span>{{ task.processed_files }} / {{ task.total_files }} 张</span>
      <span v-if="task.error_message" class="error-msg">{{ task.error_message }}</span>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ScanTask } from '@/types/scan'

const props = defineProps<{ task: ScanTask | null }>()

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    pending: '等待中', running: '扫描中', completed: '已完成', failed: '失败',
  }
  return map[props.task?.status ?? ''] ?? '—'
})

const statusType = computed(() => {
  const map: Record<string, string> = {
    pending: 'info', running: '', completed: 'success', failed: 'danger',
  }
  return map[props.task?.status ?? ''] ?? 'info'
})

const progressStatus = computed(() => {
  if (props.task?.status === 'completed') return 'success'
  if (props.task?.status === 'failed') return 'exception'
  return undefined
})
</script>

<style scoped lang="scss">
.scan-progress {
  margin-bottom: 16px;
}
.scan-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.scan-path {
  flex: 1;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.scan-bar { margin-bottom: 8px; }
.scan-meta {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  display: flex;
  justify-content: space-between;
}
.error-msg { color: var(--el-color-danger); }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
