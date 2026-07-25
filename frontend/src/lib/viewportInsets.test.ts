import { describe, expect, it } from 'vitest'

import { keyboardInset } from '@/lib/viewportInsets'

describe('keyboardInset', () => {
  it('is zero with no keyboard and the keyboard height with one', () => {
    expect(keyboardInset({ innerHeight: 844, viewportHeight: 844, offsetTop: 0 })).toBe(0)
    expect(keyboardInset({ innerHeight: 844, viewportHeight: 508, offsetTop: 0 })).toBe(336)
  })

  it('ignores a gap too small to be a keyboard', () => {
    // Browser chrome sliding away, not keys.
    expect(keyboardInset({ innerHeight: 844, viewportHeight: 760, offsetTop: 0 })).toBe(0)
  })

  it('does not double-count a layout viewport the browser already shrank', () => {
    // Chrome with `interactive-widget=resizes-content`: both heights moved, so
    // `dvh` already accounts for the keyboard and this must add nothing.
    expect(keyboardInset({ innerHeight: 508, viewportHeight: 508, offsetTop: 0 })).toBe(0)
  })

  it('subtracts a scrolled visual viewport', () => {
    // Safari scrolls the layout viewport up on focus; that offset is not keys.
    expect(keyboardInset({ innerHeight: 844, viewportHeight: 508, offsetTop: 60 })).toBe(276)
  })

  it('reads a pinch-zoomed page as no keyboard', () => {
    expect(keyboardInset({ innerHeight: 844, viewportHeight: 422, offsetTop: 0, scale: 2 })).toBe(0)
  })
})
