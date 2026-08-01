/**
 * When to shout that it's your turn. Pure — no Vue, no DOM, no audio.
 *
 * A token rather than a boolean, because "my turn started" is an edge that being
 * the active player can't see on its own: consecutive turns in a solo room never
 * flip it, and `game_started` opens a round without bumping `turnSeq`.
 */

import type { GameState } from '@/game/reducer'

/** Identity of the turn currently mine, or null. Every change is a new turn. */
export function turnToken(state: GameState, uuid: string): string | null {
  return state.activePlayerUuid === uuid ? String(state.turnSeq) : null
}

/**
 * A turn arriving from elsewhere, rather than one following my own. Keeps a solo
 * room from chiming down the clock all game.
 */
export function isArrival(before: string | null, now: string | null): boolean {
  return before === null && now !== null
}

/** The tab title, marked while it's your turn so a background tab says so. */
export function turnTitle(alerting: boolean, base: string): string {
  return alerting ? `▶ Your turn — ${base}` : base
}
