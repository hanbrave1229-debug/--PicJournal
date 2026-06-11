import axios from 'axios'
import type {
  DiaryGenerateDraftRequest,
  DiaryGenerateDraftResponse,
  DiaryMonthResponse,
  DiaryResponse,
  DiaryUpsertRequest,
} from '@/types/diary'

const BASE = '/api/v1/diaries'

export const diaryApi = {
  /**
   * Fetch all diary entries for a given month.
   * Used to populate the calendar grid.
   */
  getMonth(year: number, month: number): Promise<{ data: DiaryMonthResponse }> {
    return axios.get(`${BASE}/month`, { params: { year, month } })
  },

  /** Get a single diary entry by date string (YYYY-MM-DD). */
  getByDate(diaryDate: string): Promise<{ data: DiaryResponse }> {
    return axios.get(`${BASE}/date/${diaryDate}`)
  },

  /** Create or update a diary entry (upsert). */
  save(body: DiaryUpsertRequest): Promise<{ data: DiaryResponse }> {
    return axios.post(`${BASE}/save`, body)
  },

  /** Delete the diary entry for a given date. */
  deleteByDate(diaryDate: string): Promise<void> {
    return axios.delete(`${BASE}/date/${diaryDate}`)
  },

  /** Call AI to generate a draft for a given date. */
  generateDraft(body: DiaryGenerateDraftRequest): Promise<{ data: DiaryGenerateDraftResponse }> {
    return axios.post(`${BASE}/generate-draft`, body)
  },
}
