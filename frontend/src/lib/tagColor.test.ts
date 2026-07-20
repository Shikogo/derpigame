import { describe, expect, it } from 'vitest'

import { CATEGORY_COLORS, categoryColor, categoryPillStyle } from '@/lib/tagColor'

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

describe('categoryPillStyle', () => {
  it('tints the fill with the same hue as the text', () => {
    const style = categoryPillStyle('artist')
    const color = categoryColor('artist')
    expect(style.color).toBe(color)
    expect(style.backgroundColor).toBe(`color-mix(in srgb, ${color} 14%, transparent)`)
  })
})
