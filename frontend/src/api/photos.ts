import api from './index'
import type { Photo, PhotoListParams, PhotoListResponse } from '@/types/photo'

export const photoApi = {
  list(params: PhotoListParams = {}) {
    return api.get<PhotoListResponse>('/photos', { params })
  },

  get(id: number) {
    return api.get<Photo>(`/photos/${id}`)
  },

  delete(id: number) {
    return api.delete<{ id: number; deleted: boolean }>(`/photos/${id}`)
  },

  /** Build thumbnail URL for a given photo id and size */
  thumbnailUrl(id: number, size: 256 | 1080 = 256): string {
    return `/api/v1/thumbnails/${id}?size=${size}`
  },
}
