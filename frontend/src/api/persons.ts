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

  /** Lock or unlock a person (locked = cannot be deleted) */
  lock(id: number, locked: boolean): Promise<{ data: Person }> {
    return axios.patch(`${BASE}/${id}/lock`, null, { params: { locked } })
  },

  /** Delete a person and their face data (photos are kept). Returns 423 if locked. */
  deletePerson(id: number): Promise<void> {
    return axios.delete(`${BASE}/${id}`)
  },

  /** Merge source into target (source is deleted, faces reassigned to target) */
  merge(sourceId: number, targetId: number): Promise<{ data: { ok: boolean; message: string } }> {
    return axios.post(`${BASE}/merge`, { source_id: sourceId, target_id: targetId })
  },

  /** Get photos containing a specific person */
  photos(id: number, page = 1, pageSize = 80): Promise<{ data: PhotoListResponse }> {
    return axios.get(`${BASE}/${id}/photos`, { params: { page, page_size: pageSize } })
  },

  /** One-time backfill: populate cover_path for persons that are missing one */
  rebuildCovers(): Promise<{ data: { updated: number; still_missing: number } }> {
    return axios.post(`${BASE}/rebuild-covers`)
  },

  /** Build URL for a face crop image by filesystem path */
  cropUrl(coverPath: string | null): string {
    if (!coverPath) return ''
    const filename = coverPath.split('/').pop() ?? ''
    return `/api/v1/persons/crops/${filename}`
  },
}
