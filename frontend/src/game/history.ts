/**
 * Join the room's win counts onto the current member list for display. The
 * tally itself is authoritative from the backend (`room_state.win_counts`);
 * this is pure presentation — no game logic.
 */

import type { RoomUser, WinCount } from '@/types/wire'

export interface RoomUserWithWins extends RoomUser {
  wins: number
}

/** Decorate the current member list with each player's win count (0 if none). */
export function withWins(users: RoomUser[], counts: WinCount[]): RoomUserWithWins[] {
  const byUuid = new Map(counts.map((count) => [count.uuid, count.wins]))
  return users.map((user) => ({ ...user, wins: byUuid.get(user.uuid) ?? 0 }))
}
