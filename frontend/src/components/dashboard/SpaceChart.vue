<template>
  <el-card shadow="never" class="space-chart-card">
    <template #header><span>存储空间分析</span></template>
    <v-chart :option="option" style="height: 260px;" autoresize />
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { formatBytes } from '@/utils/format'

use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{
  totalBytes: number
  reclaimableBytes: number
}>()

const option = computed(() => {
  const used = props.totalBytes - props.reclaimableBytes
  return {
    tooltip: {
      trigger: 'item',
      formatter: (p: { name: string; value: number }) => `${p.name}: ${formatBytes(p.value)}`,
    },
    legend: { bottom: 0, left: 'center' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      data: [
        { value: used, name: '有效照片', itemStyle: { color: '#409eff' } },
        { value: props.reclaimableBytes, name: '可释放空间', itemStyle: { color: '#f56c6c' } },
      ],
    }],
  }
})
</script>
