/**
 * Derive the running win count per player from the room's finished rounds.
 * History is the single source of truth — no separate tally is stored — so this
 * is a pure function over the records, unit-testable in isolation.
 */

import type { RoomUser, RoundRecord } from '@/types/wire'

export interface WinTally {
  uuid: string
  name: string
  wins: number
}

export interface RoomUserWithWins extends RoomUser {
  wins: number
}

/** Wins per player across all rounds, most wins first. */
export function tallyWins(records: RoundRecord[]): WinTally[] {
  const tallies = new Map<string, WinTally>()
  for (const record of records) {
    for (const winner of record.winners) {
      const existing = tallies.get(winner.uuid)
      if (existing) {
        existing.wins += 1
        existing.name = winner.name // keep the most recent display name
      } else {
        tallies.set(winner.uuid, { uuid: winner.uuid, name: winner.name, wins: 1 })
      }
    }
  }
  return [...tallies.values()].sort((a, b) => b.wins - a.wins)
}

/** Decorate the current member list with each player's win count (0 if none). */
export function withWins(users: RoomUser[], tallies: WinTally[]): RoomUserWithWins[] {
  const byUuid = new Map(tallies.map((tally) => [tally.uuid, tally.wins]))
  return users.map((user) => ({ ...user, wins: byUuid.get(user.uuid) ?? 0 }))
}