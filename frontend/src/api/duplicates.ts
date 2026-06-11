import api from './index'
import type { DuplicateGroup, ResolveRequest } from '@/types/duplicate'

export const duplicateApi = {
  run(scan_task_id?: number) {
    return api.post<{ message: string }>('/duplicates/run', null, {
      params: scan_task_id != null ? { scan_task_id } : {},
    })
  },

  list() {
    return api.get<DuplicateGroup[]>('/duplicates')
  },

  get(id: number) {
    return api.get<DuplicateGroup>(`/duplicates/${id}`)
  },

  resolve(payload: ResolveRequest) {
    return api.post<{ group_id: number; kept: number; deleted: number }>(
      '/duplicates/resolve',
      payload,
    )
  },
}
