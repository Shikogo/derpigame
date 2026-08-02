/**
 * Local display preferences, persisted in `localStorage`.
 *
 * Streamer mode: the room code is a standing invitation, so streaming or
 * screen-sharing a game hands it to every viewer. Turning this on masks the code
 * wherever the app draws it and keeps it out of the address bar. Off by default.
 *
 * Sound: the chime when your turn arrives while you're looking elsewhere. On by
 * default — missing your turn is the problem it exists for, so it has to work
 * before anyone goes looking for the switch.
 *
 * Seen rules: whether the how-to-play card has come up. One-way, so a browser
 * that's played before doesn't get it again.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

const STREAMER_MODE_KEY = 'derpigame:streamerMode'
const SOUND_KEY = 'derpigame:sound'
const SEEN_RULES_KEY = 'derpigame:seenRules'

/** The persisted streamer-mode preference, off for anything unset. */
export function loadStreamerMode(storage: Storage = localStorage): boolean {
  return storage.getItem(STREAMER_MODE_KEY) === 'true'
}

/** The persisted sound preference, on unless it was explicitly turned off. */
export function loadSound(storage: Storage = localStorage): boolean {
  return storage.getItem(SOUND_KEY) !== 'false'
}

/** Whether the rules card has been shown — false when unset, so a new browser gets it. */
export function loadSeenRules(storage: Storage = localStorage): boolean {
  return storage.getItem(SEEN_RULES_KEY) === 'true'
}

export const usePreferencesStore = defineStore('preferences', () => {
  const streamerMode = ref(loadStreamerMode())
  const sound = ref(loadSound())
  const seenRules = ref(loadSeenRules())

  function setStreamerMode(value: boolean): void {
    streamerMode.value = value
    localStorage.setItem(STREAMER_MODE_KEY, String(value))
  }

  function toggleStreamerMode(): void {
    setStreamerMode(!streamerMode.value)
  }

  function setSound(value: boolean): void {
    sound.value = value
    localStorage.setItem(SOUND_KEY, String(value))
  }

  function toggleSound(): void {
    setSound(!sound.value)
  }

  function markRulesSeen(): void {
    seenRules.value = true
    localStorage.setItem(SEEN_RULES_KEY, 'true')
  }

  return {
    streamerMode,
    setStreamerMode,
    toggleStreamerMode,
    sound,
    setSound,
    toggleSound,
    seenRules,
    markRulesSeen,
  }
})
