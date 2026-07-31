/**
 * Local display preferences. Right now that's streamer mode: the room code is a
 * standing invitation, so streaming or screen-sharing a game hands it to every
 * viewer. Turning this on masks the code wherever the app draws it and keeps it
 * out of the address bar. Off by default, persisted in `localStorage`.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

const STREAMER_MODE_KEY = 'derpigame:streamerMode'

/** The persisted streamer-mode preference, off for anything unset. */
export function loadStreamerMode(storage: Storage = localStorage): boolean {
  return storage.getItem(STREAMER_MODE_KEY) === 'true'
}

export const usePreferencesStore = defineStore('preferences', () => {
  const streamerMode = ref(loadStreamerMode())

  function setStreamerMode(value: boolean): void {
    streamerMode.value = value
    localStorage.setItem(STREAMER_MODE_KEY, String(value))
  }

  function toggle(): void {
    setStreamerMode(!streamerMode.value)
  }

  return { streamerMode, setStreamerMode, toggle }
})
