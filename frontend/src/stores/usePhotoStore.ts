import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { photoApi } from '@/api/photos'
import type { Photo, PhotoListParams } from '@/types/photo'

export const usePhotoStore = defineStore('photo', () => {
  const photos = ref<Photo[]>([])
  const total = ref(0)
  const loading = ref(false)

  const params = ref<PhotoListParams>({
    page: 1,
    page_size: 80,
    sort_by: 'taken_at',
    order: 'desc',
  })

  const hasMore = computed(() =>
    photos.value.length < total.value,
  )

  async function fetchPage(reset = false) {
    if (loading.value) return
    if (reset) {
      params.value.page = 1
      photos.value = []
    }
    loading.value = true
    try {
      const { data } = await photoApi.list(params.value)
      if (reset) {
        photos.value = data.items
      } else {
        photos.value.push(...data.items)
      }
      total.value = data.total
    } finally {
      loading.value = false
    }
  }

  async function fetchNextPage() {
    if (!hasMore.value || loading.value) return
    params.value.page = (params.value.page ?? 1) + 1
    await fetchPage(false)
  }

  async function softDelete(id: number) {
    await photoApi.delete(id)
    photos.value = photos.value.filter((p) => p.id !== id)
    total.value -= 1
  }

  function setFilter(partial: Partial<PhotoListParams>) {
    Object.assign(params.value, partial)
    fetchPage(true)
  }

  return {
    photos,
    total,
    loading,
    params,
    hasMore,
    fetchPage,
    fetchNextPage,
    softDelete,
    setFilter,
  }
})
