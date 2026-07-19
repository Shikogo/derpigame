import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useGameStore } from '@/stores/game'
import type { GameEvent, Player } from '@/types/wire'

const p = (uuid: string): Player => ({ uuid, name: uuid, score: 0, wrong_guesses: 0 })

const openRound = (roster: string[]): GameEvent[] => [
  { type: 'image_started', id: '1', thumb_url: 't', full_url: 'f' },
  {
    type: 'game_started',
    first_player: p(roster[0]),
    players: roster.map(p),
    tag_count: 1,
    bonus_counts: {},
    freebie_tags: [],
    turn_seconds: 30,
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
