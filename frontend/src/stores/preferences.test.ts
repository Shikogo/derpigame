import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { loadStreamerMode, usePreferencesStore } from '@/stores/preferences'

describe('preferences store', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('defaults streamer mode off, and reads a persisted on', () => {
    expect(loadStreamerMode()).toBe(false)
    expect(usePreferencesStore().streamerMode).toBe(false)

    localStorage.setItem('derpigame:streamerMode', 'true')
    setActivePinia(createPinia())
    expect(usePreferencesStore().streamerMode).toBe(true)
  })

  it('toggle flips and persists both ways', () => {
    const prefs = usePreferencesStore()

    prefs.toggle()
    expect(prefs.streamerMode).toBe(true)
    expect(localStorage.getItem('derpigame:streamerMode')).toBe('true')

    prefs.toggle()
    expect(prefs.streamerMode).toBe(false)
    expect(localStorage.getItem('derpigame:streamerMode')).toBe('false')
  })
})
