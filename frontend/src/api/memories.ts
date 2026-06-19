import api from './index'
import type { Photo } from '@/types/photo'

export interface MemoryGroup {
  year: number
  years_ago: number
  count: number
  photos: Photo[]
}

export interface OnThisDayResponse {
  date: string
  total: number
  groups: MemoryGroup[]
}

export interface MemoryCards {
  on_this_day: {
    date: string
    count: number
    years: number[]
    cover_id: number | null
  }
}

export const memoriesApi = {
  /** 那年今日 — 历年同月同日照片，按年份分组 */
  onThisDay(): Promise<{ data: OnThisDayResponse }> {
    return api.get('/memories/on-this-day')
  },

  /** 首页回忆卡片摘要（数量 + 封面） */
  cards(): Promise<{ data: MemoryCards }> {
    return api.get('/memories/cards')
  },
}
