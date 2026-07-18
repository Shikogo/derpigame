import { describe, expect, it } from 'vitest'

import { tallyWins, withWins } from './history'
import type { Player, RoomUser, RoundRecord } from '@/types/wire'

function player(uuid: string, name: string): Player {
  return { uuid, name, score: 0, wrong_guesses: 0 }
}

function round(winners: Player[], over: Partial<RoundRecord> = {}): RoundRecord {
  return {
    page_url: 'https://derpibooru.org/images/1',
    source_url: null,
    thumb_url: 't',
    artists: [],
    win: winners.length > 0,
    aborted: false,
    winners,
    standings: [],
    ...over,
  }
}

describe('tallyWins', () => {
  it('is empty with no rounds', () => {
    expect(tallyWins([])).toEqual([])
  })

  it('counts a win per player per round and sorts most-wins first', () => {
    const alice = player('a', 'Alice')
    const bob = player('b', 'Bob')
    const tally = tallyWins([round([alice]), round([bob]), round([alice])])
    expect(tally).toEqual([
      { uuid: 'a', name: 'Alice', wins: 2 },
      { uuid: 'b', name: 'Bob', wins: 1 },
    ])
  })

  it('credits every winner of a shared round', () => {
    const tally = tallyWins([round([player('a', 'Alice'), player('b', 'Bob')])])
    expect(tally.map((t) => t.wins)).toEqual([1, 1])
  })

  it('ignores aborted and lost rounds (no winners)', () => {
    const aborted = round([], { aborted: true })
    const lost = round([], { win: false })
    expect(tallyWins([aborted, lost])).toEqual([])
  })

  it('tracks a player by uuid and keeps their most recent name', () => {
    const tally = tallyWins([round([player('a', 'Alice')]), round([player('a', 'Alicia')])])
    expect(tally).toEqual([{ uuid: 'a', name: 'Alicia', wins: 2 }])
  })
})

describe('withWins', () => {
  const user = (uuid: string, name: string): RoomUser => ({ uuid, name, ready: false })

  it('joins each current member with their win count, 0 when none', () => {
    const users = [user('a', 'Alice'), user('b', 'Bob')]
    const tallies = [{ uuid: 'a', name: 'Alice', wins: 3 }]
    expect(withWins(users, tallies)).toEqual([
      { uuid: 'a', name: 'Alice', ready: false, wins: 3 },
      { uuid: 'b', name: 'Bob', ready: false, wins: 0 },
    ])
  })

  it('drops wins of players no longer in the room', () => {
    const tallies = [{ uuid: 'gone', name: 'Ghost', wins: 5 }]
    expect(withWins([user('a', 'Alice')], tallies)).toEqual([
      { uuid: 'a', name: 'Alice', ready: false, wins: 0 },
    ])
  })
})