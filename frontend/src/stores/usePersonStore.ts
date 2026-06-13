import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { personsApi } from '@/api/persons'
import type { Person, FaceRunResponse } from '@/types/person'
import type { Photo } from '@/types/photo'

export const usePersonStore = defineStore('person', () => {
  const persons = ref<Person[]>([])
  const loading = ref(false)
  const running = ref(false)
  const lastRunResult = ref<FaceRunResponse | null>(null)

  // Active person whose photos are displayed below the strip
  const activePerson = ref<Person | null>(null)
  const activePhotos = ref<Photo[]>([])
  const activePhotosTotal = ref(0)
  const loadingPhotos = ref(false)

  /** Total non-hidden persons */
  const total = computed(() => persons.value.filter((p) => !p.is_hidden).length)

  // Fetch persons
  async function fetchPersons(includeHidden = false) {
    loading.value = true
    try {
      const { data } = await personsApi.list(includeHidden)
      persons.value = data
    } finally {
      loading.value = false
    }
  }

  // Run face analysis
  async function runAnalysis(force = false): Promise<FaceRunResponse> {
    running.value = true
    try {
      const { data } = await personsApi.run(force)
      lastRunResult.value = data
      await fetchPersons()
      return data
    } finally {
      running.value = false
    }
  }

  // Select active person -> load their photos
  async function selectPerson(person: Person) {
    if (activePerson.value?.id === person.id) return
    activePerson.value = person
    activePhotos.value = []
    activePhotosTotal.value = 0
    loadingPhotos.value = true
    try {
      const { data } = await personsApi.photos(person.id, 1, 80)
      activePhotos.value = data.items
      activePhotosTotal.value = data.total
    } finally {
      loadingPhotos.value = false
    }
  }

  // Rename
  async function renamePerson(id: number, name: string) {
    const { data } = await personsApi.rename(id, name)
    _patchLocal(data)
    if (activePerson.value?.id === id) activePerson.value = data
  }

  // Hide
  async function hidePerson(id: number, hidden: boolean) {
    const { data } = await personsApi.hide(id, hidden)
    _patchLocal(data)
  }

  // Lock
  async function lockPerson(id: number, locked: boolean) {
    const { data } = await personsApi.lock(id, locked)
    _patchLocal(data)
  }

  // Delete person (keep photos)
  async function deletePerson(id: number) {
    await personsApi.deletePerson(id)
    persons.value = persons.value.filter((p) => p.id !== id)
    if (activePerson.value?.id === id) {
      activePerson.value = null
      activePhotos.value = []
      activePhotosTotal.value = 0
    }
  }

  // Merge persons
  async function mergePersons(sourceId: number, targetId: number) {
    await personsApi.merge(sourceId, targetId)
    await fetchPersons()
    if (activePerson.value?.id === sourceId) {
      const target = persons.value.find((p) => p.id === targetId) ?? null
      if (target) await selectPerson(target)
    }
  }

  function _patchLocal(updated: Person) {
    const idx = persons.value.findIndex((p) => p.id === updated.id)
    if (idx !== -1) persons.value[idx] = updated
  }

  return {
    persons,
    loading,
    running,
    lastRunResult,
    activePerson,
    activePhotos,
    activePhotosTotal,
    loadingPhotos,
    total,
    fetchPersons,
    runAnalysis,
    selectPerson,
    renamePerson,
    hidePerson,
    lockPerson,
    deletePerson,
    mergePersons,
  }
})
