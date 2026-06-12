import api from './index'

export interface DashboardStats {
  total_photos: number
  total_size_bytes: number
  duplicate_count: number
  reclaimable_bytes: number
  blurry_count: number
  underexposed_count: number
  overexposed_count: number
  ai_tagged_count: number
  total_persons: number
  last_scan_at: string | null
  last_scan_path: string | null
}

export const dashboardApi = {
  stats() {
    return api.get<DashboardStats>('/dashboard/stats')
  },
}
