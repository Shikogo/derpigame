import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { loadSound, loadStreamerMode, usePreferencesStore } from '@/stores/preferences'

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

    prefs.toggleStreamerMode()
    expect(prefs.streamerMode).toBe(true)
    expect(localStorage.getItem('derpigame:streamerMode')).toBe('true')

    prefs.toggleStreamerMode()
    expect(prefs.streamerMode).toBe(false)
    expect(localStorage.getItem('derpigame:streamerMode')).toBe('false')
  })

  // The opposite default to streamer mode, and the reason the two loaders read
  // the stored value differently: an unset key has to mean "on" here.
  it('defaults sound on, and reads a persisted off', () => {
    expect(loadSound()).toBe(true)
    expect(usePreferencesStore().sound).toBe(true)

    localStorage.setItem('derpigame:sound', 'false')
    setActivePinia(createPinia())
    expect(usePreferencesStore().sound).toBe(false)
  })

  it('toggling sound flips and persists', () => {
    const prefs = usePreferencesStore()

    prefs.toggleSound()
    expect(prefs.sound).toBe(false)
    expect(localStorage.getItem('derpigame:sound')).toBe('false')

    prefs.toggleSound()
    expect(prefs.sound).toBe(true)
    expect(localStorage.getItem('derpigame:sound')).toBe('true')
  })
})
