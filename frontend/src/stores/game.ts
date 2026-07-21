/**
 * Holds the current `GameState` and folds each `game_events` batch into it via
 * the pure reducer. All logic lives in `@/game/reducer`; this store is just the
 * reactive shell plus a few view-facing getters.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { type GameState, concludeRound, initialGameState, reduceAll } from '@/game/reducer'
import { useSessionStore } from '@/stores/session'
import type { GameEvent, Player } from '@/types/wire'

/**
 * Longest a decided round will wait on its outro before showing the results.
 *
 * The guess overlay normally ends `ending` as soon as it has shown the last
 * cards, but it is only mounted while the game panel is — behind the age gate,
 * say, it never is. This is the backstop that guarantees a round always reaches
 * its results.
 */
const MAX_OUTRO_MS = 3000

export const useGameStore = defineStore('game', () => {
  const state = ref<GameState>(initialGameState())
  const session = useSessionStore()
  let outroTimer: ReturnType<typeof setTimeout> | undefined

  /** Fold an ordered `game_events` batch into the state (the store's one job). */
  function applyEvents(events: GameEvent[]): void {
    const was = state.value.status
    state.value = reduceAll(state.value, events)
    if (state.value.status === 'ending' && was !== 'ending') {
      clearTimeout(outroTimer)
      outroTimer = setTimeout(finishRound, MAX_OUTRO_MS)
    }
  }

  /** End a decided round's outro and show the results. */
  function finishRound(): void {
    clearTimeout(outroTimer)
    state.value = concludeRound(state.value)
  }

  function reset(): void {
    clearTimeout(outroTimer)
    state.value = initialGameState()
  }

  const activePlayer = computed<Player | null>(() => {
    const uuid = state.value.activePlayerUuid
    return uuid ? (state.value.players[uuid] ?? null) : null
  })

  const isMyTurn = computed(() => state.value.activePlayerUuid === session.uuid)

  const scoreboard = computed<Player[]>(() =>
    Object.values(state.value.players).sort((a, b) => b.score - a.score),
  )

  const ended = computed(() => state.value.status === 'over' || state.value.status === 'aborted')

  // The round's locked roster (seeded from game_started); the room store diffs
  // it against the membership list to find spectators.
  const roundPlayerUuids = computed(() => new Set(Object.keys(state.value.players)))

  // I'm spectating if a round is live but I'm not in its roster (not-ready at
  // start, or a late join) — distinct from a player waiting their turn.
  const isSpectating = computed(
    () => state.value.status === 'active' && !state.value.players[session.uuid],
  )

  return {
    state,
    applyEvents,
    finishRound,
    reset,
    activePlayer,
    isMyTurn,
    isSpectating,
    scoreboard,
    ended,
    roundPlayerUuids,
  }
})
