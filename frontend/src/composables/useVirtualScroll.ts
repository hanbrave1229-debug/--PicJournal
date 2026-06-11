/**
 * useVirtualScroll — wraps @tanstack/vue-virtual for a fixed-column photo grid.
 *
 * Given a flat list of items and a container ref, calculates which rows
 * are currently visible and provides the CSS transform for each.
 *
 * Usage:
 *   const { virtualRows, totalHeight, containerRef } = useVirtualScroll({
 *     items,
 *     columns,
 *     itemHeight: 220,
 *   })
 */
import { computed, ref, type Ref } from 'vue'
import { useVirtualizer } from '@tanstack/vue-virtual'
import type { Photo } from '@/types/photo'

export interface UseVirtualScrollOptions {
  /** Reactive flat list of all items */
  items: Ref<Photo[]>
  /** Number of columns in the grid */
  columns: Ref<number>
  /** Fixed row height in pixels (thumbnail + caption) */
  itemHeight?: number
  /** Extra rows rendered outside the visible window (improves scroll smoothness) */
  overscan?: number
}

export function useVirtualScroll({
  items,
  columns,
  itemHeight = 220,
  overscan = 5,
}: UseVirtualScrollOptions) {
  const containerRef = ref<HTMLElement | null>(null)

  /** Group flat photo list into rows of `columns` items */
  const rows = computed<Photo[][]>(() => {
    const cols = columns.value
    const result: Photo[][] = []
    for (let i = 0; i < items.value.length; i += cols) {
      result.push(items.value.slice(i, i + cols))
    }
    return result
  })

  const virtualizer = useVirtualizer(
    computed(() => ({
      count: rows.value.length,
      getScrollElement: () => containerRef.value,
      estimateSize: () => itemHeight,
      overscan,
    })),
  )

  const virtualRows = computed(() => virtualizer.value.getVirtualItems())
  const totalHeight = computed(() => virtualizer.value.getTotalSize())

  return {
    containerRef,
    rows,
    virtualRows,
    totalHeight,
  }
}
