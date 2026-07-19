import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import GuessFeed from '@/components/GuessFeed.vue'
import type { FeedEntry } from '@/game/reducer'
import { useGameStore } from '@/stores/game'

beforeEach(() => {
  setActivePinia(createPinia())
})

// One entry of every feed kind, keyed by seq so we can locate each badge.
const FEED: FeedEntry[] = [
  { seq: 1, kind: 'correct', player: 'alice', guess: 'mare', tag_type: 'species' },
  { seq: 2, kind: 'wrong', player: 'bob', guess: 'stallion', closeness: 40 },
  { seq: 3, kind: 'timeout', player: 'carol' },
  { seq: 4, kind: 'eliminated', player: 'dave' },
  { seq: 5, kind: 'rejected', guess: 'safe', reason: 'rating_tag' },
]

describe('GuessFeed', () => {
  it('shows an empty note when there are no guesses', () => {
    const wrapper = mount(GuessFeed)
    expect(wrapper.text()).toContain('No guesses yet.')
    expect(wrapper.findAll('span')).toHaveLength(0)
  })

  it('renders a color-coded badge per event type, newest first', () => {
    const game = useGameStore()
    game.state.feed = FEED

    const wrapper = mount(GuessFeed)
    const badges = wrapper.findAll('span')

    // Newest-first: the rejected entry (seq 5) leads, correct (seq 1) trails.
    expect(badges).toHaveLength(5)
    expect(badges[0].text()).toBe('safe — rating tag')
    expect(badges[4].text()).toBe('alice: mare · species')

    // Each kind carries its own tone classes.
    const byText = (t: string) => badges.find((b) => b.text() === t)!
    expect(byText('alice: mare · species').classes()).toEqual(
      expect.arrayContaining(['bg-correct/10', 'text-correct']),
    )
    expect(byText('bob: stallion · 40%').classes()).toEqual(
      expect.arrayContaining(['bg-wrong/10', 'text-wrong']),
    )
    expect(byText('carol timed out').classes()).toEqual(
      expect.arrayContaining(['bg-eliminated/10', 'text-eliminated']),
    )
    expect(byText('dave eliminated').classes()).toEqual(
      expect.arrayContaining(['bg-eliminated/10', 'text-eliminated']),
    )
    expect(byText('safe — rating tag').classes()).toEqual(
      expect.arrayContaining(['bg-raised', 'text-ink-faint']),
    )
  })

  it('omits the closeness suffix on a wrong guess with zero closeness', () => {
    const game = useGameStore()
    game.state.feed = [{ seq: 1, kind: 'wrong', player: 'bob', guess: 'x', closeness: 0 }]

    const wrapper = mount(GuessFeed)
    expect(wrapper.find('span').text()).toBe('bob: x')
  })
})
