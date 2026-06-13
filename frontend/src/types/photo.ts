/** EXIF metadata extracted from image file */
export interface ExifInfo {
  taken_at: string | null
  camera_make: string | null
  camera_model: string | null
  aperture: string | null
  shutter_speed: string | null
  iso: number | null
  gps_lat: number | null
  gps_lon: number | null
}

/** OpenCV quality scores */
export interface PhotoScores {
  /** Laplacian variance — higher = sharper. < 100 typically blurry */
  sharpness_score: number | null
  /** 0.0 = very dark, 1.0 = very bright */
  exposure_score: number | null
}

/** Full photo entity returned by the API */
export interface Photo {
  id: number
  file_path: string
  file_name: string
  file_ext: string
  file_size: number
  width: number | null
  height: number | null
  md5_hash: string | null
  phash: string | null
  thumbnail_256: string | null
  thumbnail_1080: string | null
  is_deleted: boolean
  duplicate_group_id: number | null
  exif: ExifInfo
  scores: PhotoScores
  /** AI-generated scene description (null until tagged) */
  ai_caption: string | null
  /** AI-generated keyword tags (empty until tagged) */
  ai_tags: string[]
  /** ThumbHash Base64 placeholder for progressive loading */
  thumbhash: string | null
  /** Offline reverse geocoding — country */
  country: string | null
  /** Offline reverse geocoding — province */
  province: string | null
  /** Offline reverse geocoding — city */
  city: string | null
  /** Archived photos are hidden from the main timeline */
  is_archived: boolean
  /** UUID of the burst stack this photo belongs to (null = standalone) */
  stack_id: string | null
  /** True for the representative photo of a stack */
  is_stack_cover: boolean
  created_at: string
  updated_at: string
}

/** Paginated list response */
export interface PhotoListResponse {
  total: number
  page: number
  page_size: number
  items: Photo[]
}

/** Query params for GET /api/v1/photos */
export interface PhotoListParams {
  page?: number
  page_size?: number
  sort_by?: 'taken_at' | 'file_size' | 'width' | 'height' | 'sharpness_score' | 'exposure_score' | 'created_at'
  order?: 'asc' | 'desc'
  only_duplicates?: boolean
  min_sharpness?: number
  /** Filter: only photos taken on or after this date (YYYY-MM-DD) */
  date_from?: string
  /** Filter: only photos taken on or before this date (YYYY-MM-DD) */
  date_to?: string
}
