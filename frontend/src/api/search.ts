import api from './index'
import type { Photo } from '@/types/photo'

export interface NLSearchRequest {
  query: string
  limit?: number
}

export interface NLSearchResponse {
  query: string
  where_clause: string
  total: number
  items: Photo[]
}

export const searchApi = {
  /**
   * Natural-language photo search via LLM-generated SQL.
   * Requires AI API key configured in settings.
   */
  nlSearch(body: NLSearchRequest) {
    return api.post<NLSearchResponse>('/search/nl', body)
  },
}
