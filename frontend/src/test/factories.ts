/**
 * Builders for wire payloads used across the test suite.
 *
 * `RoomState` fields are non-optional, so every new one breaks every test that
 * builds a snapshot by hand — this keeps that to one edit. Vitest only collects
 * `.test.ts` / `.spec.ts`, so this file is a plain module.
 */

import type { RoomState } from '@/types/wire'

/** A default lobby snapshot, overridable field by field. */
export function roomState(over: Partial<RoomState> = {}): RoomState {
  return {
    room: 'r',
    query: [],
    nsfw: false,
    in_progress: false,
    turn_seconds: 30,
    users: [],
    history: [],
    win_counts: [],
    ...over,
  }
}
