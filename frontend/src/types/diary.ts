/** Mood options aligned with backend MoodType literal */
export type MoodType = 'happy' | 'calm' | 'tired' | 'sad' | 'energetic'

export interface DiaryResponse {
  id: number
  diary_date: string          // ISO date "YYYY-MM-DD"
  content: string | null
  ai_draft: string | null
  mood: MoodType
  photo_ids: number[]         // cover photo is first
  photo_count: number
  cover_photo_id: number | null
  cover_thumbnail_url: string | null
  created_at: string
  updated_at: string
}

export interface DiaryCalendarItem {
  diary_date: string          // "YYYY-MM-DD"
  mood: MoodType
  summary: string | null      // first 80 chars of content
  cover_thumbnail_url: string | null
  photo_count: number
}

export interface DiaryMonthResponse {
  year: number
  month: number
  entries: DiaryCalendarItem[]
}

export interface DiaryUpsertRequest {
  diary_date: string
  content: string | null
  mood: MoodType
  photo_ids: number[]
  cover_photo_id?: number | null
}

export interface DiaryGenerateDraftRequest {
  diary_date: string
  photo_ids: number[]
  mood: MoodType
}

export interface DiaryGenerateDraftResponse {
  draft: string
}

/** Frontend-only: a calendar cell (either filled or empty) */
export interface CalendarCell {
  day: number                  // 1–31 (0 = padding)
  isPadding: boolean
  diary: DiaryCalendarItem | null
}

/** Mood display config */
export interface MoodConfig {
  name: MoodType
  emoji: string
  label: string
  color: string
}
