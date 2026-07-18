/**
 * Holds the current `GameState` and folds each `game_events` batch into it via
 * the pure reducer. All logic lives in `@/game/reducer`; this store is just the
 * reactive shell plus a few view-facing getters.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { type GameState, initialGameState, reduceAll } from '@/game/reducer'
import { useSessionStore } from '@/stores/session'
import type { GameEvent, Player } from '@/types/wire'

export const useGameStore = defineStore('game', () => {
  const state = ref<GameState>(initialGameState())
  const session = useSessionStore()

  /** Fold an ordered `game_events` batch into the state (the store's one job). */
  function applyEvents(events: GameEvent[]): void {
    state.value = reduceAll(state.value, events)
  }

  function reset(): void {
    state.value = initialGameState()
  }

  const activePlayer = computed<Player | null>(() => {
    const uuid = state.value.activePlayerUuid
    return uuid ? (state.value.players[uuid] ?? null) : null
  })

  const isMyTurn = computed(
    () =>
      state.value.activePlayerUuid === session.uuid,
  )

  const scoreboard = computed<Player[]>(() =>
    Object.values(state.value.players).sort((a, b) => b.score - a.score),
  )

  const ended = computed(
    () => state.value.status === 'over' || state.value.status === 'aborted',
  )

  return { state, applyEvents, reset, activePlayer, isMyTurn, scoreboard, ended }
})
