import api from './index'

export interface CheckResponse {
  existing: string[]
  missing: string[]
}

export interface UploadResponse {
  saved: number
  skipped_duplicate: number
  skipped_invalid: string[]
  dest_path: string
  scan_task_id: number | null
}

export const backupApi = {
  /** Ask the server which MD5 checksums already exist (so we skip uploading them). */
  check(checksums: string[]): Promise<{ data: CheckResponse }> {
    return api.post('/backup/check', { checksums })
  },

  /**
   * Upload a batch of files. Server hashes each and skips duplicates.
   * Long timeout + optional progress callback for large media.
   */
  upload(
    files: File[],
    onProgress?: (pct: number) => void,
  ): Promise<{ data: UploadResponse }> {
    const form = new FormData()
    for (const f of files) form.append('files', f, f.name)
    return api.post('/backup/upload', form, {
      timeout: 0, // no timeout — large videos can take a while
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    })
  },
}
