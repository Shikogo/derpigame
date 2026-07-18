import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { loadOrCreateUuid, useSessionStore } from '@/stores/session'

describe('session store', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('mints a uuid once and reuses it from storage', () => {
    const first = loadOrCreateUuid()
    expect(first).toBeTruthy()
    expect(loadOrCreateUuid()).toBe(first)
    expect(useSessionStore().uuid).toBe(first)
  })

  it('nsfwAck defaults to false with nothing stored', () => {
    expect(useSessionStore().nsfwAck).toBe(false)
  })

  it('acknowledgeNsfw flips the flag and persists it', () => {
    const session = useSessionStore()
    session.acknowledgeNsfw()
    expect(session.nsfwAck).toBe(true)
    expect(localStorage.getItem('derpigame:nsfwAck')).toBe('true')
  })

  it('reads a persisted acknowledgement on init', () => {
    localStorage.setItem('derpigame:nsfwAck', 'true')
    setActivePinia(createPinia())
    expect(useSessionStore().nsfwAck).toBe(true)
  })
})
