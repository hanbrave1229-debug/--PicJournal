import axios from 'axios'
import type { Person, FaceRunResponse, FaceRunStatus } from '@/types/person'
import type { PhotoListResponse } from '@/types/photo'

const BASE = '/api/v1/persons'

export const personsApi = {
  /** Run face detection + clustering pipeline */
  run(force = false): Promise<{ data: FaceRunResponse }> {
    return axios.post(`${BASE}/run`, null, { params: { force } })
  },

  /** Check pipeline run status */
  status(): Promise<{ data: FaceRunStatus }> {
    return axios.get(`${BASE}/status`)
  },

  /** List all persons (with photo counts) */
  list(includeHidden = false): Promise<{ data: Person[] }> {
    return axios.get(BASE, { params: { include_hidden: includeHidden } })
  },

  /** Get single person by ID */
  get(id: number): Promise<{ data: Person }> {
    return axios.get(`${BASE}/${id}`)
  },

  /** Rename a person */
  rename(id: number, name: string): Promise<{ data: Person }> {
    return axios.patch(`${BASE}/${id}/name`, { name })
  },

  /** Hide or unhide a person */
  hide(id: number, hidden: boolean): Promise<{ data: Person }> {
    return axios.patch(`${BASE}/${id}/hide`, null, { params: { hidden } })
  },

  /** Merge source into target */
  merge(sourceId: number, targetId: number): Promise<{ data: { ok: boolean; message: string } }> {
    return axios.post(`${BASE}/merge`, { source_id: sourceId, target_id: targetId })
  },

  /** Get photos containing a specific person */
  photos(id: number, page = 1, pageSize = 80): Promise<{ data: PhotoListResponse }> {
    return axios.get(`${BASE}/${id}/photos`, { params: { page, page_size: pageSize } })
  },

  /** Build URL for a face crop image by filename */
  cropUrl(coverPath: string | null): string {
    if (!coverPath) return ''
    const filename = coverPath.split('/').pop() ?? ''
    return `/api/v1/persons/crops/${filename}`
  },
}
