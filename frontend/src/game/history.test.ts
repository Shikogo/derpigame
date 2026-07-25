import { describe, expect, it } from 'vitest'

import { withWins } from './history'
import { roomUser } from '@/test/factories'
import type { WinCount } from '@/types/wire'

const user = (uuid: string, name: string) => roomUser(uuid, { name })

describe('withWins', () => {
  it('joins each current member with their win count, 0 when none', () => {
    const users = [user('a', 'Alice'), user('b', 'Bob')]
    const counts: WinCount[] = [{ uuid: 'a', name: 'Alice', wins: 3 }]
    expect(withWins(users, counts)).toEqual([
      { uuid: 'a', name: 'Alice', ready: false, viewing_results: false, wins: 3 },
      { uuid: 'b', name: 'Bob', ready: false, viewing_results: false, wins: 0 },
    ])
  })

  it('drops wins of players no longer in the room', () => {
    const counts: WinCount[] = [{ uuid: 'gone', name: 'Ghost', wins: 5 }]
    expect(withWins([user('a', 'Alice')], counts)).toEqual([
      { uuid: 'a', name: 'Alice', ready: false, viewing_results: false, wins: 0 },
    ])
  })
})
