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
  { seq: 1, kind: 'correct', player: 'alice', guess: 'mare' },
  { seq: 2, kind: 'wrong', player: 'bob', guess: 'stallion' },
  { seq: 4, kind: 'near_miss', player: 'carol', guess: 'applejck', closeness: 94 },
  { seq: 5, kind: 'timeout', player: 'carol' },
  { seq: 6, kind: 'eliminated', player: 'dave' },
  { seq: 7, kind: 'rejected', guess: 'safe', reason: 'rating_tag' },
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

    // Newest-first: the rejected entry (seq 7) leads, correct (seq 1) trails.
    expect(badges).toHaveLength(6)
    expect(badges[0].text()).toBe('safe — rating tag')
    expect(badges[5].text()).toBe('alice: mare')

    // Each kind carries its own tone classes.
    const byText = (t: string) => badges.find((b) => b.text() === t)!
    expect(byText('alice: mare').classes()).toEqual(
      expect.arrayContaining(['bg-correct/10', 'text-correct']),
    )
    // A wrong guess is red; a near miss (free retry) is yellow.
    expect(byText('bob: stallion').classes()).toEqual(
      expect.arrayContaining(['bg-wrong/10', 'text-wrong']),
    )
    expect(byText('carol: applejck · 94%').classes()).toEqual(
      expect.arrayContaining(['bg-very-close/10', 'text-very-close']),
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
})
