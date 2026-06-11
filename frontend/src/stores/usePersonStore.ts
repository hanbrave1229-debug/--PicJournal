import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { personsApi } from '@/api/persons'
import type { Person, FaceRunResponse, FaceRunStatus } from '@/types/person'

export const usePersonStore = defineStore('person', () => {
  const persons = ref<Person[]>([])
  const loading = ref(false)
  const running = ref(false)
  const lastRunResult = ref<FaceRunResponse | null>(null)

  /** Total non-hidden persons */
  const total = computed(() => persons.value.filter((p) => !p.is_hidden).length)

  // ── Fetch persons ──────────────────────────────────────────────────────────
  async function fetchPersons(includeHidden = false) {
    loading.value = true
    try {
      const { data } = await personsApi.list(includeHidden)
      persons.value = data
    } finally {
      loading.value = false
    }
  }

  // ── Run face analysis ──────────────────────────────────────────────────────
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

  // ── Rename ─────────────────────────────────────────────────────────────────
  async function renamePerson(id: number, name: string) {
    const { data } = await personsApi.rename(id, name)
    const idx = persons.value.findIndex((p) => p.id === id)
    if (idx !== -1) persons.value[idx] = data
  }

  // ── Hide ───────────────────────────────────────────────────────────────────
  async function hidePerson(id: number, hidden: boolean) {
    const { data } = await personsApi.hide(id, hidden)
    const idx = persons.value.findIndex((p) => p.id === id)
    if (idx !== -1) persons.value[idx] = data
  }

  // ── Merge ──────────────────────────────────────────────────────────────────
  async function mergePersons(sourceId: number, targetId: number) {
    await personsApi.merge(sourceId, targetId)
    await fetchPersons()
  }

  return {
    persons,
    loading,
    running,
    lastRunResult,
    total,
    fetchPersons,
    runAnalysis,
    renamePerson,
    hidePerson,
    mergePersons,
  }
})
