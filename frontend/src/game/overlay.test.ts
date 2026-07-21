import { describe, expect, it } from 'vitest'

import { overlayCard, overlayCards } from './overlay'
import type { FeedEntry } from './reducer'

const LIMIT = 3

function card(entry: FeedEntry, limit = LIMIT) {
  return overlayCard(entry, limit)
}

describe('overlayCard', () => {
  it('skips freebies, which arrive as a batch nobody guessed', () => {
    expect(card({ seq: 1, kind: 'freebie', guess: 'pony' })).toBeNull()
  })

  it('names the player and the bucket on a correct guess', () => {
    const c = card({
      seq: 2,
      kind: 'correct',
      player: 'Shiko',
      guess: 'twilight sparkle',
      tagType: 'tags',
      remaining: 11,
    })
    expect(c).toMatchObject({
      tone: 'correct',
      player: 'Shiko',
      headline: 'twilight sparkle',
      detail: '11 left',
      bucket: 'tags',
    })
    expect(c?.strikes).toBeUndefined()
  })

  it('uses the bucket key as its own label when a bucket is cleared', () => {
    // Taxonomy keys are already plural, so they read as a label unsuffixed.
    expect(
      card({
        seq: 3,
        kind: 'correct',
        player: 'Ari',
        guess: 'artist:x',
        tagType: 'artists',
        remaining: 0,
      })?.detail,
    ).toBe('all artists found')
  })

  it('counts only the strikes taken, never padding to the limit', () => {
    const first = card({ seq: 4, kind: 'wrong', player: 'Ari', guess: 'rainbow dash', strike: 1 })
    expect(first).toMatchObject({ tone: 'wrong', detail: 'strike 1 of 3' })
    expect(first?.strikes).toEqual({ used: 1, limit: 3 })

    const second = card({ seq: 5, kind: 'wrong', player: 'Ari', guess: 'applejack', strike: 2 })
    expect(second?.strikes).toEqual({ used: 2, limit: 3 })
  })

  it('escalates the eliminating strike to the out tone', () => {
    const c = card({ seq: 6, kind: 'wrong', player: 'Ari', guess: 'fluttershy', strike: 3 })
    expect(c).toMatchObject({ tone: 'out', detail: 'eliminated' })
    expect(c?.strikes).toEqual({ used: 3, limit: 3 })
  })

  it('tracks a non-default strike limit', () => {
    expect(card({ seq: 7, kind: 'wrong', player: 'Ari', guess: 'x', strike: 2 }, 5)).toMatchObject({
      tone: 'wrong',
      detail: 'strike 2 of 5',
    })
  })

  it('carries the typed original only when the server translated it', () => {
    const aliased = card({
      seq: 8,
      kind: 'correct',
      player: 'Shiko',
      guess: 'twilight sparkle',
      tagType: 'tags',
      remaining: 4,
      asTyped: 'twilight',
    })
    expect(aliased?.asTyped).toBe('twilight')

    const plain = card({
      seq: 9,
      kind: 'correct',
      player: 'Shiko',
      guess: 'twilight sparkle',
      tagType: 'tags',
      remaining: 4,
    })
    expect(plain?.asTyped).toBeUndefined()
  })

  it('reports a near miss as a free retry, with no strike', () => {
    const c = card({ seq: 10, kind: 'near_miss', player: 'Shiko', guess: 'twilite', closeness: 92 })
    expect(c).toMatchObject({ tone: 'near', detail: 'so close · 92% · free retry' })
    expect(c?.strikes).toBeUndefined()
  })

  it('spells a timeout out rather than showing an empty guess', () => {
    const c = card({ seq: 11, kind: 'timeout', player: 'Ari', strike: 1 })
    expect(c).toMatchObject({ tone: 'wrong', player: 'Ari', headline: 'ran out of time' })
    expect(c?.strikes).toEqual({ used: 1, limit: 3 })
  })

  it('blames nobody for a rejected guess and keeps it muted', () => {
    expect(card({ seq: 12, kind: 'rejected', guess: 'safe', reason: 'rating_tag' })).toMatchObject({
      tone: 'muted',
      player: null,
      headline: 'safe',
      detail: 'rating tag',
    })
  })

  it('marks an elimination as out', () => {
    expect(card({ seq: 13, kind: 'eliminated', player: 'Ari' })).toMatchObject({
      tone: 'out',
      player: 'Ari',
      headline: 'is out',
    })
  })
})
describe('overlayCards', () => {
  const strikeOut: FeedEntry = { seq: 1, kind: 'wrong', player: 'Ari', guess: 'x', strike: 3 }
  const eliminated: FeedEntry = { seq: 2, kind: 'eliminated', player: 'Ari' }

  it('drops the elimination that follows its own third strike', () => {
    const cards = overlayCards([strikeOut, eliminated], LIMIT)
    expect(cards).toHaveLength(1)
    expect(cards[0]).toMatchObject({ seq: 1, tone: 'out', detail: 'eliminated' })
  })

  it('keeps an elimination that follows someone else being struck out', () => {
    const other: FeedEntry = { seq: 2, kind: 'eliminated', player: 'Shiko' }
    expect(overlayCards([strikeOut, other], LIMIT)).toHaveLength(2)
  })

  it('keeps an elimination that no strike accounts for', () => {
    const survivable: FeedEntry = { seq: 1, kind: 'wrong', player: 'Ari', guess: 'x', strike: 1 }
    expect(overlayCards([survivable, eliminated], LIMIT)).toHaveLength(2)
  })

  it('merges a timeout that eliminated the same way', () => {
    const timedOut: FeedEntry = { seq: 1, kind: 'timeout', player: 'Ari', strike: 3 }
    expect(overlayCards([timedOut, eliminated], LIMIT)).toHaveLength(1)
  })

  it('returns only entries newer than the watermark', () => {
    const feed: FeedEntry[] = [
      { seq: 1, kind: 'correct', player: 'A', guess: 'a', tagType: 'tags', remaining: 2 },
      { seq: 2, kind: 'correct', player: 'B', guess: 'b', tagType: 'tags', remaining: 1 },
    ]
    expect(overlayCards(feed, LIMIT, 1).map((c) => c.seq)).toEqual([2])
  })

  it('still judges a new entry against one already seen', () => {
    // The strike is below the watermark, but it is what makes the elimination
    // a repeat — so the rule has to see the whole feed, not just the new slice.
    expect(overlayCards([strikeOut, eliminated], LIMIT, 1)).toHaveLength(0)
  })

  it('skips freebies in a sequence too', () => {
    const feed: FeedEntry[] = [
      { seq: 1, kind: 'freebie', guess: 'pony' },
      { seq: 2, kind: 'freebie', guess: 'safe' },
    ]
    expect(overlayCards(feed, LIMIT)).toEqual([])
  })
})
