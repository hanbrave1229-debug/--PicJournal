import axios from 'axios'
import type {
  Album,
  AlbumCreateRequest,
  AlbumListResponse,
  AlbumPhotosResponse,
  AlbumUpdateRequest,
  TrashListResponse,
} from '@/types/album'
import type { PhotoListResponse } from '@/types/photo'

const BASE = '/api/v1/albums'
const TRASH = '/api/v1/trash'

export const albumsApi = {
  // ── Album CRUD ──────────────────────────────────────────────────────────────

  /** List all user albums (excludes smart albums) */
  list(): Promise<{ data: AlbumListResponse }> {
    return axios.get(BASE)
  },

  /** Get a single album by ID */
  get(id: number): Promise<{ data: Album }> {
    return axios.get(`${BASE}/${id}`)
  },

  /** Create a new album */
  create(body: AlbumCreateRequest): Promise<{ data: Album }> {
    return axios.post(BASE, body)
  },

  /** Update album title / description / cover */
  update(id: number, body: AlbumUpdateRequest): Promise<{ data: Album }> {
    return axios.patch(`${BASE}/${id}`, body)
  },

  /** Delete an album (does NOT delete the photos inside) */
  delete(id: number): Promise<void> {
    return axios.delete(`${BASE}/${id}`)
  },

  // ── Album photos ────────────────────────────────────────────────────────────

  /** Paginated photos inside an album */
  photos(id: number, page = 1, pageSize = 60): Promise<{ data: AlbumPhotosResponse }> {
    return axios.get(`${BASE}/${id}/photos`, { params: { page, page_size: pageSize } })
  },

  /** Add photos to an album; silently ignores duplicates */
  addPhotos(id: number, photoIds: number[]): Promise<{ data: { added: number } }> {
    return axios.post(`${BASE}/${id}/photos`, { photo_ids: photoIds })
  },

  /** Remove specific photos from an album */
  removePhotos(id: number, photoIds: number[]): Promise<{ data: { removed: number } }> {
    return axios.delete(`${BASE}/${id}/photos`, { data: { photo_ids: photoIds } })
  },

  // ── Smart albums ────────────────────────────────────────────────────────────

  /** List all smart (conditional) albums */
  listSmart(): Promise<{ data: AlbumListResponse }> {
    return axios.get(`${BASE}/smart`)
  },

  /** Create a smart album with rule JSON */
  createSmart(body: AlbumCreateRequest): Promise<{ data: Album }> {
    return axios.post(BASE, { ...body, is_smart: true })
  },

  /** Dynamically evaluate a smart album and return matching photos */
  evaluate(id: number, page = 1, pageSize = 60): Promise<{ data: PhotoListResponse }> {
    return axios.post(`${BASE}/${id}/evaluate`, null, {
      params: { page, page_size: pageSize },
    })
  },
}

export const trashApi = {
  // ── Trash ───────────────────────────────────────────────────────────────────

  /** Paginated list of soft-deleted photos */
  list(page = 1, pageSize = 60): Promise<{ data: TrashListResponse }> {
    return axios.get(TRASH, { params: { page, page_size: pageSize } })
  },

  /** Restore a photo from the trash */
  restore(photoId: number): Promise<{ data: { restored: number } }> {
    return axios.post(`${TRASH}/${photoId}/restore`)
  },

  /** Permanently delete a single photo from trash */
  hardDelete(photoId: number): Promise<void> {
    return axios.delete(`${TRASH}/${photoId}`)
  },

  /** Permanently delete all photos in the trash */
  emptyTrash(): Promise<{ data: { deleted: number } }> {
    return axios.delete(TRASH)
  },

  /** Soft-delete a photo (move to trash) — called from Gallery / ImageViewer */
  softDelete(photoId: number): Promise<{ data: { deleted: number } }> {
    return axios.delete(`/api/v1/photos/${photoId}`)
  },
}
