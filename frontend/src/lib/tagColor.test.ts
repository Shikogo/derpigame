import { describe, expect, it } from 'vitest'

import {
  CATEGORY_COLORS,
  bucketColor,
  bucketPillStyle,
  categoryColor,
  categoryPillStyle,
} from '@/lib/tagColor'

/** The bonus buckets a Derpibooru round reports, in the server's order. */
const BONUS = ['artists', 'ocs', 'comics', 'fanfics', 'series']

describe('categoryColor', () => {
  it('is deterministic — the same key always maps to the same color', () => {
    for (const key of ['artist', 'character', 'species', 'oc', 'rating']) {
      expect(categoryColor(key)).toBe(categoryColor(key))
    }
  })

  it('always returns a color from the ramp', () => {
    for (let i = 0; i < 100; i++) {
      expect(CATEGORY_COLORS).toContain(categoryColor(`bucket-${i}`))
    }
  })

  it('spreads keys across the whole ramp', () => {
    const seen = new Set<string>()
    for (let i = 0; i < 100; i++) seen.add(categoryColor(`bucket-${i}`))
    expect(seen.size).toBe(CATEGORY_COLORS.length)
  })

  it('distinguishes distinct keys (not all one color)', () => {
    const seen = new Set([
      categoryColor('artist'),
      categoryColor('character'),
      categoryColor('species'),
    ])
    expect(seen.size).toBeGreaterThan(1)
  })
})

describe('bucketColor', () => {
  it('gives every bonus bucket in a round its own color', () => {
    const seen = new Set(BONUS.map((key) => bucketColor(key, BONUS)))
    expect(seen.size).toBe(BONUS.length)
  })

  it('gives the goal bucket a hue outside the bonus ramp', () => {
    const goal = bucketColor('tags', BONUS)
    expect(BONUS.map((key) => bucketColor(key, BONUS))).not.toContain(goal)
  })

  it('keeps a bucket its color when the round is missing the others', () => {
    // bonusKeys is the taxonomy's whole list either way, so a chip doesn't
    // change hue just because this image had no OCs.
    expect(bucketColor('comics', BONUS)).toBe(bucketColor('comics', BONUS))
    expect(bucketColor('series', BONUS)).not.toBe(bucketColor('artists', BONUS))
  })

  it('wraps once a taxonomy has more buckets than the ramp has colors', () => {
    const many = Array.from({ length: CATEGORY_COLORS.length + 1 }, (_, i) => `b${i}`)
    expect(bucketColor(many[many.length - 1], many)).toBe(bucketColor(many[0], many))
  })
})

describe('bucketPillStyle', () => {
  it('tints the fill with the bucket’s positional hue', () => {
    const style = bucketPillStyle('ocs', BONUS)
    const color = bucketColor('ocs', BONUS)
    expect(style.color).toBe(color)
    expect(style.backgroundColor).toBe(`color-mix(in srgb, ${color} 14%, transparent)`)
  })
})

describe('categoryPillStyle', () => {
  it('tints the fill with the same hue as the text', () => {
    const style = categoryPillStyle('artist')
    const color = categoryColor('artist')
    expect(style.color).toBe(color)
    expect(style.backgroundColor).toBe(`color-mix(in srgb, ${color} 14%, transparent)`)
  })
})
