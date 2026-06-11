import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { duplicateApi } from '@/api/duplicates'
import type { DuplicateGroup, ResolveRequest } from '@/types/duplicate'

export const useDuplicateStore = defineStore('duplicate', () => {
  const groups = ref<DuplicateGroup[]>([])
  const loading = ref(false)

  const exactGroups = computed(() => groups.value.filter((g) => g.group_type === 'exact'))
  const similarGroups = computed(() => groups.value.filter((g) => g.group_type === 'similar'))
  const burstGroups = computed(() => groups.value.filter((g) => g.group_type === 'burst'))

  const totalReclaimable = computed(() =>
    groups.value.reduce((sum, g) => {
      // Sum file sizes of all non-recommended photos in each group
      return sum + g.photos
        .filter((p) => p.id !== g.recommended_keep_id)
        .reduce((s, p) => s + p.file_size, 0)
    }, 0),
  )

  async function fetchGroups() {
    loading.value = true
    try {
      const { data } = await duplicateApi.list()
      groups.value = data
    } finally {
      loading.value = false
    }
  }

  async function runDedup() {
    await duplicateApi.run()
  }

  async function resolve(payload: ResolveRequest) {
    await duplicateApi.resolve(payload)
    groups.value = groups.value.filter((g) => g.id !== payload.group_id)
  }

  return {
    groups,
    loading,
    exactGroups,
    similarGroups,
    burstGroups,
    totalReclaimable,
    fetchGroups,
    runDedup,
    resolve,
  }
})
