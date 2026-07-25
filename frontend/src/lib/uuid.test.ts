import { afterEach, describe, expect, it, vi } from 'vitest'

import { randomUuid } from '@/lib/uuid'

const V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('randomUuid', () => {
  it('returns a v4 uuid from the real environment', () => {
    expect(randomUuid()).toMatch(V4)
  })

  it('assembles one by hand where randomUUID is missing (plain-http origin)', () => {
    // Counting bytes: half of them are single hex digits, so a uuid that came
    // out of unpadded bytes lands somewhere else entirely.
    vi.stubGlobal('crypto', {
      getRandomValues: (bytes: Uint8Array) => bytes.map((_, i) => i),
    })

    expect(randomUuid()).toBe('00010203-0405-4607-8809-0a0b0c0d0e0f')
  })
})
