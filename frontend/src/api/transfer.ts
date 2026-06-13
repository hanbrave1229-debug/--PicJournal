/**
 * transfer.ts — Export & Import API helpers
 */
import api from './index'

// ── Export ────────────────────────────────────────────────────────────────────

/**
 * Download selected photo IDs as a ZIP file.
 * Uses a hidden <a> tag so the browser shows the native download UI.
 */
export async function downloadPhotosZip(photoIds: number[], filename = 'photos_export'): Promise<void> {
  const res = await api.post(
    '/export/photos',
    { photo_ids: photoIds, filename },
    { responseType: 'blob' },
  )
  _triggerDownload(res.data as Blob, `${filename}.zip`)
}

/** Download all photos in one album as a ZIP. */
export async function downloadAlbumZip(albumId: number, albumTitle = 'album'): Promise<void> {
  const res = await api.get(`/export/album/${albumId}`, { responseType: 'blob' })
  _triggerDownload(res.data as Blob, `${albumTitle}.zip`)
}

/** Download multiple albums in one ZIP (sub-folders per album). */
export async function downloadAlbumsZip(albumIds: number[], filename = 'albums_export'): Promise<void> {
  const res = await api.post(
    '/export/albums',
    { album_ids: albumIds, filename },
    { responseType: 'blob' },
  )
  _triggerDownload(res.data as Blob, `${filename}.zip`)
}

function _triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 5000)
}

// ── Import ────────────────────────────────────────────────────────────────────

export interface ImportPhotosResult {
  saved: number
  skipped: string[]
  dest_path: string
  scan_task_id: number
}

export interface ImportAlbumZipResult {
  album_id: number
  album_name: string
  saved: number
  skipped: string[]
  dest_path: string
  status: string
}

export interface ImportFromLibraryResult {
  album_id: number
  album_name: string
  added: number
}

/** Get detected library root directory. */
export async function getScanRoot(): Promise<string | null> {
  const res = await api.get<{ root: string | null }>('/import/scan-root')
  return res.data.root
}

/** Upload photo files to library. `onProgress` receives 0-100. */
export async function importPhotos(
  files: File[],
  subdir: string,
  onProgress?: (pct: number) => void,
): Promise<ImportPhotosResult> {
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  form.append('subdir', subdir)

  // Do NOT set Content-Type manually — axios auto-sets multipart/form-data with boundary
  const res = await api.post<ImportPhotosResult>('/import/photos', form, {
    onUploadProgress: e => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
    },
  })
  return res.data
}

/** Upload a ZIP archive and create an album from it. */
export async function importAlbumFromZip(
  file: File,
  albumName: string,
  subdir: string,
  onProgress?: (pct: number) => void,
): Promise<ImportAlbumZipResult> {
  const form = new FormData()
  form.append('file', file)
  form.append('album_name', albumName)
  form.append('subdir', subdir)

  // Do NOT set Content-Type manually — axios auto-sets multipart/form-data with boundary
  const res = await api.post<ImportAlbumZipResult>('/import/album/zip', form, {
    onUploadProgress: e => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
    },
  })
  return res.data
}

/** Create a new album from existing library photo IDs. */
export async function importAlbumFromLibrary(
  photoIds: number[],
  albumName: string,
): Promise<ImportFromLibraryResult> {
  const res = await api.post<ImportFromLibraryResult>('/import/album/from-library', {
    photo_ids: photoIds,
    album_name: albumName,
  })
  return res.data
}
