import axios from 'axios'
import type { Photo } from '@/types/photo'

const BASE = '/api/v1/shares'

export interface ShareInfo {
  token: string
  album_id: number
  album_title: string
  has_password: boolean
  expires_at: string | null
  view_count: number
  created_at: string
}

export interface PublicShareMeta {
  album_title: string
  photo_count: number
  needs_password: boolean
  cover_id: number | null
}

export interface PublicPhotosResponse {
  items: Photo[]
  total: number
  page: number
  page_size: number
}

export const sharesApi = {
  /** Create a share link for an album. */
  create(albumId: number, password?: string | null, expiresDays?: number | null) {
    return axios.post<ShareInfo>(BASE, {
      album_id: albumId,
      password: password || null,
      expires_days: expiresDays || null,
    })
  },

  /** List all share links for an album. */
  listForAlbum(albumId: number) {
    return axios.get<ShareInfo[]>(`${BASE}/album/${albumId}`)
  },

  /** Revoke a share link. */
  revoke(token: string) {
    return axios.delete(`${BASE}/${token}`)
  },

  // ── Public (no auth) ──────────────────────────────────────────────────────
  publicMeta(token: string) {
    return axios.get<PublicShareMeta>(`${BASE}/public/${token}`)
  },

  publicPhotos(token: string, password: string | null, page = 1, pageSize = 100) {
    return axios.post<PublicPhotosResponse>(
      `${BASE}/public/${token}/photos`,
      { password: password || null },
      { params: { page, page_size: pageSize } },
    )
  },
}
