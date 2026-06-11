import { defineStore } from 'pinia'
import { ref } from 'vue'
import { scanApi } from '@/api/scan'
import type { ScanTask } from '@/types/scan'

export const useScanStore = defineStore('scan', () => {
  const tasks = ref<ScanTask[]>([])
  const activeTask = ref<ScanTask | null>(null)
  const loading = ref(false)

  async function fetchTasks() {
    loading.value = true
    try {
      const { data } = await scanApi.list()
      tasks.value = data
      const running = data.find((t) => t.status === 'running' || t.status === 'pending')
      if (running) activeTask.value = running
    } finally {
      loading.value = false
    }
  }

  async function startScan(path: string) {
    const { data } = await scanApi.start(path)
    tasks.value.unshift(data)
    activeTask.value = data
    return data
  }

  function updateActive(partial: Partial<ScanTask>) {
    if (!activeTask.value) return
    Object.assign(activeTask.value, partial)
    const idx = tasks.value.findIndex((t) => t.id === activeTask.value?.id)
    if (idx !== -1) Object.assign(tasks.value[idx], partial)
  }

  function clearActive() {
    activeTask.value = null
  }

  return { tasks, activeTask, loading, fetchTasks, startScan, updateActive, clearActive }
})
