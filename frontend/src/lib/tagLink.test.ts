import { describe, expect, it } from 'vitest'

import { tagSearchUrl } from './tagLink'

describe('tagSearchUrl', () => {
  it('builds a booru search for a multi-word tag, spaces as "+"', () => {
    expect(tagSearchUrl('rainbow dash')).toBe('https://derpibooru.org/search?q=rainbow+dash')
  })

  it('keeps a single-word tag as-is', () => {
    expect(tagSearchUrl('mare')).toBe('https://derpibooru.org/search?q=mare')
  })

  it('round-trips a namespaced tag through the query param', () => {
    const url = new URL(tagSearchUrl('artist:foo'))
    expect(url.searchParams.get('q')).toBe('artist:foo')
  })

  it('escapes characters that would otherwise break the query string', () => {
    const url = new URL(tagSearchUrl('a&b=c?d'))
    expect(url.searchParams.get('q')).toBe('a&b=c?d')
  })
})
