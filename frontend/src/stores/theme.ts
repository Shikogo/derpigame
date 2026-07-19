/**
 * Light/dark UI theme. Dark is the default (the app is dark-first); the choice
 * persists in `localStorage` and is reflected as `data-theme` on <html>, which
 * flips the color tokens defined in `style.css`.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

export type Theme = 'dark' | 'light'

const THEME_KEY = 'derpigame:theme'

/** The persisted theme, defaulting to dark for anything unset or unrecognized. */
export function loadTheme(storage: Storage = localStorage): Theme {
  return storage.getItem(THEME_KEY) === 'light' ? 'light' : 'dark'
}

/** Reflect the theme onto <html> so the CSS token overrides take effect. */
export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
  // Keep the mobile browser chrome in step with the page background.
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', theme === 'light' ? '#f3f4f8' : '#171a21')
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<Theme>(loadTheme())
  applyTheme(theme.value)

  function setTheme(value: Theme): void {
    theme.value = value
    localStorage.setItem(THEME_KEY, value)
    applyTheme(value)
  }

  function toggle(): void {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  return { theme, setTheme, toggle }
})