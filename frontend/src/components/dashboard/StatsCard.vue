<template>
  <el-card class="stats-card" shadow="hover">
    <div class="stats-body">
      <div class="stats-icon" :style="{ background: `${color}18`, color }">
        <el-icon :size="24"><component :is="icon" /></el-icon>
      </div>
      <div class="stats-info">
        <div class="stats-value">{{ value }}</div>
        <div class="stats-label">{{ label }}</div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{
  /** Display value (pre-formatted string) */
  value: string
  label: string
  /** Element Plus icon component name */
  icon: string
  /** Accent color */
  color?: string
}>()
</script>

<style scoped lang="scss">
.stats-card { border-radius: 12px; }
.stats-body {
  display: flex;
  align-items: center;
  gap: 16px;
}
.stats-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stats-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1.2;
}
.stats-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
</style>
