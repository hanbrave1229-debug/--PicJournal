import api from './index'
import type { Photo, PhotoListResponse } from '@/types/photo'

export const archiveApi = {
  /** Move a photo to the archive (hidden from main timeline). */
  archive(photoId: number) {
    return api.post<Photo>(`/archive/${photoId}`)
  },

  /** Restore an archived photo back to the main timeline. */
  unarchive(photoId: number) {
    return api.post<Photo>(`/archive/${photoId}/restore`)
  },

  /** List archived photos (paginated). */
  list(params: { page?: number; page_size?: number } = {}) {
    return api.get<PhotoListResponse>('/archive', { params })
  },
}
