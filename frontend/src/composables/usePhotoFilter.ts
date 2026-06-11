/**
 * usePhotoFilter — encapsulates filter/sort state for the gallery view.
 * Syncs changes back to the photo store.
 */
import { reactive, watch } from 'vue'
import { usePhotoStore } from '@/stores/usePhotoStore'
import type { PhotoListParams } from '@/types/photo'

export function usePhotoFilter() {
  const photoStore = usePhotoStore()

  const filter = reactive<PhotoListParams>({
    sort_by: 'taken_at',
    order: 'desc',
    only_duplicates: false,
    min_sharpness: undefined,
  })

  // Auto-apply whenever filter changes (debounced by Vue's batch update)
  watch(filter, (val) => {
    photoStore.setFilter({ ...val, page: 1 })
  })

  function reset() {
    filter.sort_by = 'taken_at'
    filter.order = 'desc'
    filter.only_duplicates = false
    filter.min_sharpness = undefined
  }

  return { filter, reset }
}
