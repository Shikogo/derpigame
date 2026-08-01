/**
 * Tells you it's your turn when the rail can't: marks the tab title, raises the
 * handoff banner, and chimes if you're looking somewhere else. Instantiated once
 * from `App.vue` for its side effects; the deciding lives in `@/game/turnAlert`.
 */

import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

import { isArrival, turnTitle, turnToken } from '@/game/turnAlert'
import { playChime, primeAudio } from '@/lib/chime'
import { useGameStore } from '@/stores/game'
import { usePreferencesStore } from '@/stores/preferences'
import { useSessionStore } from '@/stores/session'

/** How long the handoff banner holds before settling back to the plain strip. */
const BANNER_MS = 1200

export const useTurnAlertStore = defineStore('turnAlert', () => {
  const game = useGameStore()
  const session = useSessionStore()
  const prefs = usePreferencesStore()

  /** Whatever the tab was called before a turn started marking it. */
  const baseTitle = document.title

  const justArrived = ref(false)
  let bannerTimer: ReturnType<typeof setTimeout> | undefined

  // One nudge per absence: a chime you didn't come back for isn't repeated.
  let armed = true
  window.addEventListener('focus', () => {
    armed = true
  })

  primeAudio()

  const token = computed(() => turnToken(game.state, session.uuid))

  // No `immediate`: mounting into a live turn isn't a handoff. A rejoin still
  // lands one, because its `game_snapshot` arrives after this store exists.
  watch(token, (now, before) => {
    document.title = turnTitle(now !== null, baseTitle)
    if (!isArrival(before ?? null, now)) return

    justArrived.value = true
    clearTimeout(bannerTimer)
    bannerTimer = setTimeout(() => {
      justArrived.value = false
    }, BANNER_MS)

    // You're looking right at it; the banner has this covered.
    if (document.hasFocus()) {
      armed = true
      return
    }
    if (!armed || !prefs.sound) return
    armed = false
    playChime()
  })

  return { justArrived }
})
