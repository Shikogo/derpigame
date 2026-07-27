/**
 * How the roster reads between rounds: where each member is, and the one-line
 * summary under the ready/start bar. Pure — no Vue, no store.
 */

import type { RoomUser } from '@/types/wire'

/**
 * Where a member is right now. Ready wins over `viewing_results`: someone who
 * readied up from the results screen is in for the next round wherever they're
 * reading it from, and that's the more useful thing to show.
 */
export type Presence = 'ready' | 'results' | 'lobby'

export function presenceOf(user: RoomUser): Presence {
  if (user.ready) return 'ready'
  return user.viewing_results ? 'results' : 'lobby'
}

/** Nobody left to wait on: everyone in the room is in for the next round. */
export function allReady(users: RoomUser[]): boolean {
  return users.length > 0 && users.every((u) => presenceOf(u) === 'ready')
}

const names = new Intl.ListFormat('en', { type: 'conjunction' })

/**
 * The status line under the bar: how many are in for the next round, then who
 * isn't and why — a player idling in the lobby will spectate, one still on the
 * results screen may just not have looked up yet. Empty for a room of one,
 * which has no roster news to report.
 */
export function readyLine(users: RoomUser[]): string {
  if (users.length < 2) return ''
  if (allReady(users)) return `All ${users.length} ready`
  const ready = users.filter((u) => presenceOf(u) === 'ready')
  const parts = [`${ready.length} of ${users.length} ready`]
  const waiting = users.filter((u) => presenceOf(u) === 'lobby').map((u) => u.name)
  const reading = users.filter((u) => presenceOf(u) === 'results').map((u) => u.name)
  if (waiting.length) parts.push(`${names.format(waiting)} will spectate`)
  if (reading.length) {
    parts.push(
      `${names.format(reading)} ${reading.length === 1 ? 'is' : 'are'} still on the results`,
    )
  }
  return parts.join(' · ')
}
