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

export interface SemanticSearchResult {
  id: number
  thumbnail_256: string | null
  taken_at: string | null
  ai_caption: string | null
  score: number
}

export interface SemanticStatus {
  available: boolean
  total_photos: number
  embedded_photos: number
  index_size: number
}

export const searchApi = {
  /** Natural-language photo search via LLM-generated SQL */
  nlSearch(body: NLSearchRequest) {
    return api.post<NLSearchResponse>('/search/nl', body)
  },

  /** CLIP semantic text → photo search (fully offline after model download) */
  semanticSearch(query: string, topK = 40) {
    return api.post<SemanticSearchResult[]>('/semantic/search', { query, top_k: topK })
  },

  /** Status of CLIP model + embedding progress */
  semanticStatus() {
    return api.get<SemanticStatus>('/semantic/status')
  },

  /** Trigger batch CLIP embedding in background */
  startEmbedding(force = false) {
    return api.post<{ status: string; message: string }>('/semantic/embed', null, { params: { force } })
  },

  /** Find visually similar photos to a given photo */
  findSimilar(photoId: number, topK = 20) {
    return api.get<SemanticSearchResult[]>(`/semantic/similar/${photoId}`, { params: { top_k: topK } })
  },
}

// ── Stack API ──────────────────────────────────────────────────────────────────

export interface StackPhoto {
  id: number
  thumbnail_256: string | null
  taken_at: string | null
  sharpness_score: number | null
  is_stack_cover: boolean
  stack_id: string | null
}

export const stacksApi = {
  /** Trigger auto-stack analysis for the whole library */
  autoStack(force = false, dryRun = false) {
    return api.post<{ status?: string; groups_created?: number }>('/stacks/auto', null, {
      params: { force, dry_run: dryRun },
    })
  },

  /** Get all photos in a stack */
  getStack(stackId: string) {
    return api.get<StackPhoto[]>(`/stacks/${stackId}`)
  },

  /** Dissolve a stack (all photos become standalone) */
  dissolve(stackId: string) {
    return api.delete<{ ok: boolean; dissolved_count: number }>(`/stacks/${stackId}`)
  },

  /** Set a photo as the stack cover */
  setCover(stackId: string, photoId: number) {
    return api.post<{ ok: boolean }>(`/stacks/${stackId}/cover/${photoId}`)
  },

  /** Remove a photo from its stack */
  unstackPhoto(photoId: number) {
    return api.delete<{ ok: boolean }>(`/stacks/photos/${photoId}`)
  },
}
