import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { emitAck } from '@/socket/client'
import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'
import { roomState } from '@/test/factories'
import type { GameEvent, Player, RoomState, RoomUser } from '@/types/wire'

vi.mock('@/socket/client', () => ({ emitAck: vi.fn() }))

const member = (uuid: string, ready: boolean): RoomUser => ({
  uuid,
  name: uuid.toUpperCase(),
  ready,
})
const player = (uuid: string): Player => ({
  uuid,
  name: uuid.toUpperCase(),
  score: 0,
  wrong_guesses: 0,
})

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
      elimination_threshold: 3,
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

describe('room store — start pending flag', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(emitAck).mockReset()
  })

  it('stays set for the whole in-flight start, then clears', async () => {
    const room = useRoomStore()
    let settle: (ack: unknown) => void = () => {}
    vi.mocked(emitAck).mockReturnValue(new Promise((resolve) => (settle = resolve)))

    const pending = room.startGame()
    expect(room.starting).toBe(true)

    settle({ ok: true })
    await pending
    expect(room.starting).toBe(false)
  })

  it('clears when the emit rejects', async () => {
    const room = useRoomStore()
    vi.mocked(emitAck).mockRejectedValue(new Error('timeout'))

    await room.startGame()

    expect(room.starting).toBe(false)
    expect(room.error).toBe('timeout')
  })

  it('ignores a second start while one is in flight', async () => {
    const room = useRoomStore()
    vi.mocked(emitAck).mockReturnValue(new Promise(() => {})) // never settles

    room.startGame()
    const second = await room.startGame()

    expect(second).toEqual({ ok: false, error: 'game_in_progress' })
    expect(emitAck).toHaveBeenCalledTimes(1)
  })
})

describe('room store — guess pending flag', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(emitAck).mockReset()
  })

  it('stays set for the whole in-flight guess, then clears', async () => {
    const room = useRoomStore()
    let settle: (ack: unknown) => void = () => {}
    vi.mocked(emitAck).mockReturnValue(new Promise((resolve) => (settle = resolve)))

    const pending = room.submitGuess('mare')
    expect(room.guessing).toBe(true)

    settle({ ok: true })
    await pending
    expect(room.guessing).toBe(false)
  })

  it('clears when the emit rejects', async () => {
    const room = useRoomStore()
    vi.mocked(emitAck).mockRejectedValue(new Error('timeout'))

    await room.submitGuess('mare')

    expect(room.guessing).toBe(false)
    expect(room.error).toBe('timeout')
  })

  it('ignores a second guess while one is in flight', async () => {
    const room = useRoomStore()
    vi.mocked(emitAck).mockReturnValue(new Promise(() => {})) // never settles

    room.submitGuess('mare')
    const second = await room.submitGuess('pony')

    expect(second).toEqual({ ok: false, error: 'guess_in_flight' })
    expect(emitAck).toHaveBeenCalledTimes(1)
  })
})
