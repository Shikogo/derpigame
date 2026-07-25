import { describe, expect, it } from 'vitest'

import { sourceLabel } from '@/lib/sourceLabel'

const sources = [
  { key: 'derpibooru', label: 'Derpibooru' },
  { key: 'furbooru', label: 'Furbooru' },
]

describe('sourceLabel', () => {
  it('prefers the server label and capitalizes an unknown key', () => {
    expect(sourceLabel('furbooru', sources)).toBe('Furbooru')
    expect(sourceLabel('e621', sources)).toBe('E621')
  })

  it('survives an empty key and an empty picker', () => {
    expect(sourceLabel('furbooru', [])).toBe('Furbooru')
    expect(sourceLabel('', sources)).toBe('')
  })
})
