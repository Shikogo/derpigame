import { describe, expect, it } from 'vitest'

import { presenceOf, readyLine } from '@/game/lobbyStatus'
import { roomUser } from '@/test/factories'

describe('presenceOf', () => {
  it('ranks ready over a results screen still being read', () => {
    expect(presenceOf(roomUser('a', { ready: true, viewing_results: true }))).toBe('ready')
    expect(presenceOf(roomUser('b', { viewing_results: true }))).toBe('results')
    expect(presenceOf(roomUser('c'))).toBe('lobby')
  })
})

describe('readyLine', () => {
  it('names who is out and why, or just the tally when everyone is in', () => {
    const users = [
      roomUser('a', { name: 'Alice', ready: true }),
      roomUser('b', { name: 'Bob' }),
      roomUser('c', { name: 'Carol', viewing_results: true }),
      roomUser('d', { name: 'Dave', viewing_results: true }),
    ]

    expect(readyLine(users)).toBe(
      '1 of 4 ready · Bob will spectate · Carol and Dave are still on the results',
    )
    expect(readyLine(users.map((u) => ({ ...u, ready: true })))).toBe('All 4 ready')
  })

  it('has no roster news to report in a room of one', () => {
    expect(readyLine([roomUser('a', { ready: true })])).toBe('')
  })
})
