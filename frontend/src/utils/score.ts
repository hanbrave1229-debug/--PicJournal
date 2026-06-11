/**
 * Map a sharpness score (Laplacian variance) to a CSS color token.
 * < 80   → red    (blurry)
 * 80–200 → orange (acceptable)
 * > 200  → green  (sharp)
 */
export function sharpnessColor(score: number | null): string {
  if (score === null) return 'var(--el-text-color-placeholder)'
  if (score < 80) return 'var(--el-color-danger)'
  if (score < 200) return 'var(--el-color-warning)'
  return 'var(--el-color-success)'
}

/**
 * Map a sharpness score to a badge label.
 */
export function sharpnessLabel(score: number | null): string {
  if (score === null) return '未评分'
  if (score < 80) return '模糊'
  if (score < 200) return '一般'
  return '清晰'
}

/**
 * Map an exposure score (0–1) to a label.
 */
export function exposureLabel(score: number | null): string {
  if (score === null) return '未评分'
  if (score < 0.05) return '欠曝'
  if (score > 0.95) return '过曝'
  return '正常'
}

/**
 * Map an exposure score to a CSS color token.
 */
export function exposureColor(score: number | null): string {
  if (score === null) return 'var(--el-text-color-placeholder)'
  if (score < 0.05 || score > 0.95) return 'var(--el-color-danger)'
  return 'var(--el-color-success)'
}
