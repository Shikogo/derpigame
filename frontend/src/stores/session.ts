/**
 * The local player's stable identity: a `uuid` the backend keys membership on,
 * plus a display `name`. Both persist in `localStorage` so a refresh or deep
 * link keeps the same identity (and can re-join a room).
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

import { randomUuid } from '@/lib/uuid'

const UUID_KEY = 'derpigame:uuid'
const NAME_KEY = 'derpigame:name'
const NSFW_ACK_KEY = 'derpigame:nsfwAck'

/** Read the persisted identity uuid, minting and storing one on first use. */
export function loadOrCreateUuid(storage: Storage = localStorage): string {
  const existing = storage.getItem(UUID_KEY)
  if (existing) return existing
  const uuid = randomUuid()
  storage.setItem(UUID_KEY, uuid)
  return uuid
}

export const useSessionStore = defineStore('session', () => {
  const uuid = ref(loadOrCreateUuid())
  const name = ref(localStorage.getItem(NAME_KEY) ?? '')
  // One-time 18+ self-attestation, remembered per browser.
  const nsfwAck = ref(localStorage.getItem(NSFW_ACK_KEY) === 'true')

  function setName(value: string): void {
    name.value = value.trim()
    localStorage.setItem(NAME_KEY, name.value)
  }

  function acknowledgeNsfw(): void {
    nsfwAck.value = true
    localStorage.setItem(NSFW_ACK_KEY, 'true')
  }

  return { uuid, name, nsfwAck, setName, acknowledgeNsfw }
})
