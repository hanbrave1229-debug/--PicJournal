/**
 * Format a byte count into a human-readable string.
 * e.g. 1536 → "1.5 KB", 2097152 → "2.0 MB"
 */
export function formatBytes(bytes: number, decimals = 1): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`
}

/**
 * Format an ISO datetime string to a localized display string.
 * e.g. "2024-06-01T12:34:56" → "2024/06/01 12:34"
 */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Format image dimensions as "W × H px".
 */
export function formatDimensions(w: number | null, h: number | null): string {
  if (!w || !h) return '—'
  return `${w} × ${h}`
}

/**
 * Format resolution in megapixels.
 * e.g. (4000, 3000) → "12.0 MP"
 */
export function formatMegapixels(w: number | null, h: number | null): string {
  if (!w || !h) return '—'
  return `${((w * h) / 1_000_000).toFixed(1)} MP`
}
