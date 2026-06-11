import type { Photo } from './photo'

export type DuplicateType = 'exact' | 'similar' | 'burst'

export interface DuplicateGroup {
  id: number
  group_type: DuplicateType
  recommended_keep_id: number | null
  photos: Photo[]
}

export interface ResolveRequest {
  group_id: number
  keep_ids: number[]
  delete_ids: number[]
}
