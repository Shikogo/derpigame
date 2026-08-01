import { describe, expect, it } from 'vitest'

import { initialGameState, reduceAll } from '@/game/reducer'
import { isArrival, turnTitle, turnToken } from '@/game/turnAlert'
import type { GameEvent, Player } from '@/types/wire'

const p = (uuid: string): Player => ({ uuid, name: uuid, score: 0, wrong_guesses: 0 })

const openRound = (roster: string[]): GameEvent[] => [
  { type: 'image_started', id: '1', thumb_url: 't', full_url: 'f', source: 'derpibooru' },
  {
    type: 'game_started',
    first_player: p(roster[0]),
    players: roster.map(p),
    tag_count: 2,
    bonus_counts: {},
    freebie_tags: [],
    turn_seconds: 30,
    elimination_threshold: 3,
  },
]

/** Fold events onto a state, so each step reads as "and then this happened". */
const after = (events: GameEvent[], from = initialGameState()) => reduceAll(from, events)

describe('turnToken', () => {
  it('changes once per turn of mine and is null the rest of the time', () => {
    // Opening the round counts, even though `game_started` never bumps turnSeq.
    let state = after(openRound(['me', 'other']))
    const opened = turnToken(state, 'me')
    expect(opened).not.toBeNull()
    expect(turnToken(state, 'other')).toBeNull()

    // Handed away, then back — a different token, so the return is visible.
    state = after([{ type: 'turn_started', player: p('other') }], state)
    expect(turnToken(state, 'me')).toBeNull()
    state = after([{ type: 'turn_started', player: p('me') }], state)
    const returned = turnToken(state, 'me')
    expect(returned).not.toBeNull()
    expect(returned).not.toBe(opened)

    // Straight back to me (solo, or last player standing): still a new turn.
    state = after([{ type: 'turn_started', player: p('me') }], state)
    expect(turnToken(state, 'me')).not.toBe(returned)
  })

  it('holds steady through a rejected guess and a near miss', () => {
    // Neither ends the turn server-side, so neither may re-fire the banner.
    const state = after(openRound(['me', 'other']))
    const held = turnToken(state, 'me')

    const rejected = after(
      [{ type: 'guess_rejected', guess: 'mare', reason: 'already_guessed' }],
      state,
    )
    expect(turnToken(rejected, 'me')).toBe(held)

    const nearMiss = after(
      [{ type: 'near_miss', player: p('me'), guess: 'mre', closeness: 0.9 }],
      state,
    )
    expect(turnToken(nearMiss, 'me')).toBe(held)
  })

  it('goes null when the round ends under me', () => {
    const state = after(
      [
        {
          type: 'game_over',
          win: true,
          winners: [p('me')],
          standings: [p('me')],
          unguessed: {},
          win_counts: [],
        },
      ],
      after(openRound(['me'])),
    )
    expect(turnToken(state, 'me')).toBeNull()
  })
})

describe('isArrival', () => {
  it('is true only for a turn coming from elsewhere', () => {
    expect(isArrival(null, '3')).toBe(true)
    // Mine following my own — the solo/last-standing case that must stay quiet.
    expect(isArrival('3', '4')).toBe(false)
    expect(isArrival('3', null)).toBe(false)
    expect(isArrival(null, null)).toBe(false)
  })
})

describe('turnTitle', () => {
  it('marks the tab only while it is my turn', () => {
    expect(turnTitle(true, 'Derpigame')).toBe('▶ Your turn — Derpigame')
    expect(turnTitle(false, 'Derpigame')).toBe('Derpigame')
  })
})
