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
}
