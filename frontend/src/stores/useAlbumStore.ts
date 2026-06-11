import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { albumsApi, trashApi } from '@/api/albums'
import type { Album, TrashPhoto } from '@/types/album'
import type { Photo } from '@/types/photo'

export const useAlbumStore = defineStore('album', () => {
  // ── State ───────────────────────────────────────────────────────────────────
  const albums = ref<Album[]>([])
  const loadingAlbums = ref(false)

  const currentAlbum = ref<Album | null>(null)
  const currentAlbumPhotos = ref<Photo[]>([])
  const currentAlbumTotal = ref(0)
  const loadingPhotos = ref(false)

  const trashPhotos = ref<TrashPhoto[]>([])
  const trashTotal = ref(0)
  const loadingTrash = ref(false)

  // ── Getters ─────────────────────────────────────────────────────────────────
  const albumCount = computed(() => albums.value.length)

  // ── Album CRUD ──────────────────────────────────────────────────────────────

  /**
   * Load all albums into `albums`.
   */
  async function fetchAlbums() {
    loadingAlbums.value = true
    try {
      const { data } = await albumsApi.list()
      albums.value = data.items
    } finally {
      loadingAlbums.value = false
    }
  }

  /**
   * Create a new album and prepend it to the local list.
   */
  async function createAlbum(title: string, description?: string): Promise<Album> {
    const { data } = await albumsApi.create({ title, description })
    albums.value.unshift(data)
    return data
  }

  /**
   * Rename / update description / set cover for an album.
   */
  async function updateAlbum(
    id: number,
    patch: { title?: string; description?: string; cover_photo_id?: number | null },
  ) {
    const { data } = await albumsApi.update(id, patch)
    const idx = albums.value.findIndex((a) => a.id === id)
    if (idx !== -1) albums.value[idx] = data
    if (currentAlbum.value?.id === id) currentAlbum.value = data
  }

  /**
   * Delete an album (photos are NOT deleted).
   */
  async function deleteAlbum(id: number) {
    await albumsApi.delete(id)
    albums.value = albums.value.filter((a) => a.id !== id)
    if (currentAlbum.value?.id === id) currentAlbum.value = null
  }

  // ── Album photos ────────────────────────────────────────────────────────────

  /**
   * Load paginated photos for a given album into `currentAlbumPhotos`.
   */
  async function fetchAlbumPhotos(albumId: number, page = 1, pageSize = 60) {
    loadingPhotos.value = true
    try {
      const { data } = await albumsApi.photos(albumId, page, pageSize)
      if (page === 1) {
        currentAlbumPhotos.value = data.items
      } else {
        currentAlbumPhotos.value.push(...data.items)
      }
      currentAlbumTotal.value = data.total
    } finally {
      loadingPhotos.value = false
    }
  }

  /**
   * Add photos to an album; updates local photo_count on the album entry.
   */
  async function addPhotosToAlbum(albumId: number, photoIds: number[]) {
    const { data } = await albumsApi.addPhotos(albumId, photoIds)
    const idx = albums.value.findIndex((a) => a.id === albumId)
    if (idx !== -1) albums.value[idx].photo_count += data.added
    return data.added
  }

  /**
   * Remove photos from the current album view and update count.
   */
  async function removePhotosFromAlbum(albumId: number, photoIds: number[]) {
    await albumsApi.removePhotos(albumId, photoIds)
    currentAlbumPhotos.value = currentAlbumPhotos.value.filter(
      (p) => !photoIds.includes(p.id),
    )
    const idx = albums.value.findIndex((a) => a.id === albumId)
    if (idx !== -1) albums.value[idx].photo_count -= photoIds.length
    currentAlbumTotal.value -= photoIds.length
  }

  // ── Trash ───────────────────────────────────────────────────────────────────

  /**
   * Load trash photos (page=1 resets, page>1 appends).
   */
  async function fetchTrash(page = 1, pageSize = 60) {
    loadingTrash.value = true
    try {
      const { data } = await trashApi.list(page, pageSize)
      if (page === 1) {
        trashPhotos.value = data.items
      } else {
        trashPhotos.value.push(...data.items)
      }
      trashTotal.value = data.total
    } finally {
      loadingTrash.value = false
    }
  }

  /**
   * Restore a photo from trash to the library.
   */
  async function restorePhoto(photoId: number) {
    await trashApi.restore(photoId)
    trashPhotos.value = trashPhotos.value.filter((p) => p.id !== photoId)
    trashTotal.value -= 1
  }

  /**
   * Permanently delete a single photo from trash.
   */
  async function hardDeletePhoto(photoId: number) {
    await trashApi.hardDelete(photoId)
    trashPhotos.value = trashPhotos.value.filter((p) => p.id !== photoId)
    trashTotal.value -= 1
  }

  /**
   * Empty the entire trash (hard-delete all).
   */
  async function emptyTrash(): Promise<number> {
    const { data } = await trashApi.emptyTrash()
    trashPhotos.value = []
    trashTotal.value = 0
    return data.deleted
  }

  /**
   * Move a photo to the trash from Gallery / ImageViewer.
   * Returns the deleted photo ID so callers can remove it from the view.
   */
  async function softDeletePhoto(photoId: number) {
    await trashApi.softDelete(photoId)
    trashTotal.value += 1
  }

  return {
    // state
    albums,
    loadingAlbums,
    currentAlbum,
    currentAlbumPhotos,
    currentAlbumTotal,
    loadingPhotos,
    trashPhotos,
    trashTotal,
    loadingTrash,
    // getters
    albumCount,
    // album CRUD
    fetchAlbums,
    createAlbum,
    updateAlbum,
    deleteAlbum,
    // album photos
    fetchAlbumPhotos,
    addPhotosToAlbum,
    removePhotosFromAlbum,
    // trash
    fetchTrash,
    restorePhoto,
    hardDeletePhoto,
    emptyTrash,
    softDeletePhoto,
  }
})
