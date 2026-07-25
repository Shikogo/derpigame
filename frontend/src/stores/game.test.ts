import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useGameStore } from '@/stores/game'
import type { GameEvent, Player } from '@/types/wire'

const p = (uuid: string): Player => ({ uuid, name: uuid, score: 0, wrong_guesses: 0 })

const openRound = (roster: string[]): GameEvent[] => [
  { type: 'image_started', id: '1', thumb_url: 't', full_url: 'f', source: 'derpibooru' },
  {
    type: 'game_started',
    first_player: p(roster[0]),
    players: roster.map(p),
    tag_count: 1,
    bonus_counts: {},
    freebie_tags: [],
    turn_seconds: 30,
    elimination_threshold: 3,
  },
  { type: 'turn_started', player: p(roster[0]) },
]

describe('game store — isSpectating', () => {
  beforeEach(() => {
    localStorage.setItem('derpigame:uuid', 'me') // deterministic session identity
    setActivePinia(createPinia())
  })

  it('is false when I am in the round roster', () => {
    const game = useGameStore()
    game.applyEvents(openRound(['me', 'other']))
    expect(game.isSpectating).toBe(false)
  })

  it('is true when a round is live but I am not in its roster', () => {
    const game = useGameStore()
    game.applyEvents(openRound(['other']))
    expect(game.isSpectating).toBe(true)
  })

  it('is false when no round is active', () => {
    const game = useGameStore()
    expect(game.isSpectating).toBe(false)
  })
})

describe('game store — canAbort', () => {
  beforeEach(() => {
    localStorage.setItem('derpigame:uuid', 'me') // deterministic session identity
    setActivePinia(createPinia())
  })

  it('is true for a current, non-eliminated player', () => {
    const game = useGameStore()
    game.applyEvents(openRound(['me', 'other']))
    expect(game.canAbort).toBe(true)
  })

  it('is false once I am eliminated (no rage-quitting)', () => {
    const game = useGameStore()
    game.applyEvents(openRound(['me', 'other']))
    game.applyEvents([{ type: 'player_eliminated', player: p('me') }])
    expect(game.canAbort).toBe(false)
  })

  it('is false while spectating and when no round is active', () => {
    const game = useGameStore()
    expect(game.canAbort).toBe(false) // no round
    game.applyEvents(openRound(['other'])) // live round, I'm not in it
    expect(game.canAbort).toBe(false)
  })
})

describe('game store — round outro', () => {
  beforeEach(() => {
    localStorage.setItem('derpigame:uuid', 'me')
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => vi.useRealTimers())

  const gameOver: GameEvent = {
    type: 'game_over',
    win: true,
    winners: [p('me')],
    standings: [p('me')],
    win_counts: [],
    unguessed: {},
  }

  it('holds a decided round in ending, so the last cards still get shown', () => {
    const game = useGameStore()
    game.applyEvents([...openRound(['me']), gameOver])
    expect(game.state.status).toBe('ending')
    // `ended` gates the results screen — still false, so the picture stays up.
    expect(game.ended).toBe(false)
  })

  it('finishRound closes the outro on demand', () => {
    const game = useGameStore()
    game.applyEvents([...openRound(['me']), gameOver])
    game.finishRound()
    expect(game.state.status).toBe('over')
    expect(game.ended).toBe(true)
  })

  it('closes the outro on its own if nothing else does', () => {
    const game = useGameStore()
    game.applyEvents([...openRound(['me']), gameOver])
    // The overlay normally ends it, but it is only mounted with the game panel —
    // behind the age gate it never is, so a round must still reach its results.
    vi.advanceTimersByTime(3000)
    expect(game.state.status).toBe('over')
  })

  it('does not leave the backstop armed across a reset', () => {
    const game = useGameStore()
    game.applyEvents([...openRound(['me']), gameOver])
    game.reset()
    vi.advanceTimersByTime(3000)
    // A fresh round must not be closed by the previous round's timer.
    game.applyEvents(openRound(['me']))
    expect(game.state.status).toBe('active')
  })
})
