/** A unique person identified by face clustering */
export interface Person {
  id: number
  name: string
  /** Path to representative face crop served at /api/v1/persons/crops/{filename} */
  cover_path: string | null
  /** Computed URL for the cover image (derived from cover_path by backend) */
  cover_url: string | null
  is_hidden: boolean
  /** Locked persons cannot be deleted */
  is_locked: boolean
  photo_count: number
  created_at: string
  updated_at: string
  /** Up to 4 thumbnail URLs of the most recent photos containing this person */
  preview_photos: string[]
}

/** Paginated response for the persons list endpoint */
export interface PersonListResponse {
  total: number
  page: number
  page_size: number
  items: Person[]
}

/** Summary returned after running face analysis */
export interface FaceRunResponse {
  photos_processed: number
  faces_detected: number
  persons_created: number
  persons_updated: number
  message: string
}

export interface FaceRunStatus {
  running: boolean
  last_run_result: FaceRunResponse | null
}
