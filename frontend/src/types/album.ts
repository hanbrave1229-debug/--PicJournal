import type { Photo } from './photo'

/** A user-created (or smart) album */
export interface Album {
  id: number
  title: string
  description: string | null
  cover_photo_id: number | null
  is_smart: boolean
  photo_count: number
  created_at: string
  updated_at: string
}

export interface AlbumListResponse {
  items: Album[]
  total: number
}

export interface AlbumCreateRequest {
  title: string
  description?: string
}

export interface AlbumUpdateRequest {
  title?: string
  description?: string
  cover_photo_id?: number | null
}

/** Paginated photos inside an album */
export interface AlbumPhotosResponse {
  items: Photo[]
  total: number
  page: number
  page_size: number
}

/** Soft-deleted photo in the trash */
export interface TrashPhoto {
  id: number
  file_name: string
  file_path: string
  file_size: number
  thumbnail_256: string | null
  deleted_at: string | null
  taken_at: string | null
}

export interface TrashListResponse {
  items: TrashPhoto[]
  total: number
}
