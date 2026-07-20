import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { loadTheme, useThemeStore } from '@/stores/theme'

describe('theme store', () => {
  beforeEach(() => {
    localStorage.clear()
    delete document.documentElement.dataset.theme
    setActivePinia(createPinia())
  })

  it('defaults to dark with nothing stored', () => {
    expect(loadTheme()).toBe('dark')
    expect(useThemeStore().theme).toBe('dark')
  })

  it('reads a persisted theme on init', () => {
    localStorage.setItem('derpigame:theme', 'light')
    expect(useThemeStore().theme).toBe('light')
  })

  it('reflects the theme onto <html> on init', () => {
    useThemeStore()
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('toggle flips, persists, and reflects the theme', () => {
    const theme = useThemeStore()
    theme.toggle()
    expect(theme.theme).toBe('light')
    expect(localStorage.getItem('derpigame:theme')).toBe('light')
    expect(document.documentElement.dataset.theme).toBe('light')

    theme.toggle()
    expect(theme.theme).toBe('dark')
    expect(localStorage.getItem('derpigame:theme')).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })
})
