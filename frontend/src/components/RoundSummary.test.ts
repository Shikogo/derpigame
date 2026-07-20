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
  { seq: 2, kind: 'correct', player: 'alice', guess: 'mare', tagType: 'tags' },
  { seq: 3, kind: 'wrong', player: 'bob', guess: 'stallion' },
  { seq: 4, kind: 'correct', player: 'bob', guess: 'oc:nyx', tagType: 'ocs' },
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
    const text = mountWithRound().text()
    expect(text).toContain('mare')
    expect(text).toContain('alice')
    expect(text).toContain('oc:nyx')
    expect(text).toContain('free') // the freebie has no guesser
    expect(text).not.toContain('stallion') // a wrong guess is not a found tag
  })

  it('counts found and missed tags separately', () => {
    const text = mountWithRound().text()
    expect(text).toContain('Found 3') // 2 correct + 1 freebie
    expect(text).toContain('Missed 2') // across both buckets
  })

  it('labels each missed bucket and lists its tags', () => {
    const text = mountWithRound().text()
    expect(text).toContain('tags')
    expect(text).toContain('rarity')
    expect(text).toContain('artists')
    expect(text).toContain('artist:foo')
  })

  it('shows the found tags alone when the room missed nothing', () => {
    const game = useGameStore()
    game.state.feed = FEED
    const text = mount(RoundSummary).text()
    expect(text).toContain('Found 3')
    expect(text).not.toContain('Missed')
  })
})
