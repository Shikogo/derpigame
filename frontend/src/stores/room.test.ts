import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'
import { roomState } from '@/test/factories'
import type { GameEvent, Player, RoomState, RoomUser } from '@/types/wire'

const member = (uuid: string, ready: boolean): RoomUser => ({ uuid, name: uuid.toUpperCase(), ready })
const player = (uuid: string): Player => ({ uuid, name: uuid.toUpperCase(), score: 0, wrong_guesses: 0 })

function snapshot(inProgress: boolean, users: RoomUser[]): RoomState {
  return roomState({ in_progress: inProgress, users })
}

function openRound(roster: string[]): GameEvent[] {
  return [
    { type: 'image_started', id: '1', thumb_url: 't', full_url: 'f' },
    {
      type: 'game_started',
      first_player: player(roster[0]),
      players: roster.map(player),
      tag_count: 1,
      bonus_counts: {},
      freebie_tags: [],
      turn_seconds: 30,
    },
    { type: 'turn_started', player: player(roster[0]) },
  ]
}

describe('room store — spectators', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('counts members not in the round roster as spectators', () => {
    const room = useRoomStore()
    const game = useGameStore()

    room.setRoomState(snapshot(true, [member('a', true), member('b', true), member('c', false)]))
    game.applyEvents(openRound(['a', 'b'])) // c never readied → spectator

    expect(room.spectatorCount).toBe(1)
    expect(room.spectators.map((s) => s.uuid)).toEqual(['c'])
  })

  it('treats a late joiner (added mid-round, not in the roster) as a spectator', () => {
    const room = useRoomStore()
    const game = useGameStore()

    room.setRoomState(snapshot(true, [member('a', true), member('b', true)]))
    game.applyEvents(openRound(['a', 'b']))
    // A late joiner arrives; the roster is locked, so they spectate this round.
    room.setRoomState(snapshot(true, [member('a', true), member('b', true), member('d', false)]))

    expect(room.spectatorCount).toBe(1)
    expect(room.spectators.map((s) => s.uuid)).toEqual(['d'])
  })

  it('reports no spectators outside a game', () => {
    const room = useRoomStore()
    room.setRoomState(snapshot(false, [member('a', false), member('b', false)]))
    expect(room.spectatorCount).toBe(0)
  })
})
