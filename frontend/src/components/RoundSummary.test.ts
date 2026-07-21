import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import RoundSummary from '@/components/RoundSummary.vue'
import type { FeedEntry } from '@/game/reducer'
import { useGameStore } from '@/stores/game'

beforeEach(() => {
  setActivePinia(createPinia())
})

const FEED: FeedEntry[] = [
  { seq: 1, kind: 'freebie', guess: 'safe' },
  { seq: 2, kind: 'correct', player: 'alice', guess: 'mare', tagType: 'tags', remaining: 2 },
  { seq: 3, kind: 'wrong', player: 'bob', guess: 'stallion', strike: 1 },
  { seq: 4, kind: 'correct', player: 'bob', guess: 'oc:nyx', tagType: 'ocs', remaining: 0 },
]

function mountWithRound() {
  const game = useGameStore()
  game.state.feed = FEED
  game.state.unguessed = { tags: ['rarity'], artists: ['artist:foo'] }
  return mount(RoundSummary)
}

describe('RoundSummary', () => {
  it('renders nothing while a round is still running', () => {
    expect(mount(RoundSummary).find('div').exists()).toBe(false)
  })

  it('shows found tags with their guesser, and freebies as free', () => {
    const found = mountWithRound().findAll('section')[0].text()
    expect(found).toContain('mare')
    expect(found).toContain('alice')
    expect(found).toContain('oc:nyx')
    expect(found).toContain('free') // the freebie has no guesser
    expect(found).not.toContain('stallion') // a wrong guess is not a found tag
  })

  it('counts found, missed and suggested tags separately', () => {
    const text = mountWithRound().text()
    expect(text).toContain('Found 3') // 2 correct + 1 freebie
    expect(text).toContain('Missed 2') // across both buckets
    expect(text).toContain('Consider adding 1')
  })

  it('lists wrong guesses as tags to consider adding', () => {
    const suggested = mountWithRound().findAll('section').at(-1)!.text()
    expect(suggested).toContain('Consider adding')
    expect(suggested).toContain('stallion')
    expect(suggested).toContain('bob')
  })

  it('labels each missed bucket and lists its tags', () => {
    const text = mountWithRound().text()
    expect(text).toContain('tags')
    expect(text).toContain('rarity')
    expect(text).toContain('artists')
    expect(text).toContain('artist:foo')
  })

  it('links every found and missed tag to its booru search', () => {
    const links = mountWithRound().findAll('a')
    expect(links.map((a) => a.attributes('href'))).toEqual([
      'https://derpibooru.org/search?q=safe',
      'https://derpibooru.org/search?q=mare',
      'https://derpibooru.org/search?q=oc%3Anyx',
      'https://derpibooru.org/search?q=rarity',
      'https://derpibooru.org/search?q=artist%3Afoo',
    ])
  })

  it('opens tag links in a new tab without leaking the opener', () => {
    const link = mountWithRound().find('a')
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('rel')).toBe('noopener noreferrer')
  })

  it('leaves wrong guesses unlinked — they may not be real tags', () => {
    const suggested = mountWithRound().findAll('section').at(-1)!
    expect(suggested.findAll('a')).toHaveLength(0)
  })

  it('drops the missed section when the room got every tag', () => {
    const game = useGameStore()
    game.state.feed = FEED
    const text = mount(RoundSummary).text()
    expect(text).toContain('Found 3')
    expect(text).not.toContain('Missed')
    expect(text).toContain('Consider adding') // wrong guesses still stand
  })
})
