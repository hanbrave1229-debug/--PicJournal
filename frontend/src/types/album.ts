import type { Photo } from './photo'

/** Rule object for smart albums */
export interface SmartAlbumRules {
  camera_model?: string | null
  quality_score_gt?: number | null
  date_after?: string | null
  date_before?: string | null
  country?: string | null
  province?: string | null
  city?: string | null
}

/** A user-created (or smart) album */
export interface Album {
  id: number
  title: string
  description: string | null
  cover_photo_id: number | null
  is_smart: boolean
  smart_rules: string | null
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
  is_smart?: boolean
  smart_rules?: SmartAlbumRules | null
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
