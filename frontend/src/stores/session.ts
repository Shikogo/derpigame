/**
 * The local player's stable identity: a `uuid` the backend keys membership on,
 * plus a display `name`. Both persist in `localStorage` so a refresh or deep
 * link keeps the same identity (and can re-join a room).
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

const UUID_KEY = 'derpigame:uuid'
const NAME_KEY = 'derpigame:name'

/** Read the persisted identity uuid, minting and storing one on first use. */
export function loadOrCreateUuid(storage: Storage = localStorage): string {
  const existing = storage.getItem(UUID_KEY)
  if (existing) return existing
  const uuid = crypto.randomUUID()
  storage.setItem(UUID_KEY, uuid)
  return uuid
}

export const useSessionStore = defineStore('session', () => {
  const uuid = ref(loadOrCreateUuid())
  const name = ref(localStorage.getItem(NAME_KEY) ?? '')

  function setName(value: string): void {
    name.value = value.trim()
    localStorage.setItem(NAME_KEY, name.value)
  }

  return { uuid, name, setName }
})
