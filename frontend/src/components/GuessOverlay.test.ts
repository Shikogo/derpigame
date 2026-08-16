import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import GuessOverlay from '@/components/GuessOverlay.vue'
import type { FeedEntry } from '@/game/reducer'
import { useGameStore } from '@/stores/game'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

/** Append feed entries the way a `game_events` batch would, then let the watcher run. */
async function push(entries: FeedEntry[]) {
  const game = useGameStore()
  game.state.feed = [...game.state.feed, ...entries]
  await vi.advanceTimersByTimeAsync(0)
}

// Narrowed to the correct-guess variant, so callers can spread `asTyped` onto it.
const correct = (seq: number, guess = 'mare'): Extract<FeedEntry, { kind: 'correct' }> => ({
  seq,
  kind: 'correct',
  player: 'alice',
  guess,
  tagType: 'tags',
  remaining: 3,
})

describe('GuessOverlay', () => {
  it('shows nothing until a guess lands', () => {
    const wrapper = mount(GuessOverlay)
    expect(wrapper.text()).toBe('')
  })

  it('shows a landing guess, then clears it after the hold', async () => {
    const wrapper = mount(GuessOverlay)
    await push([correct(1)])
    expect(wrapper.text()).toContain('mare')
    expect(wrapper.text()).toContain('alice')

    await vi.advanceTimersByTimeAsync(1500)
    expect(wrapper.text()).not.toContain('mare')
  })

  it('never shows freebies, which would flood the round opening', async () => {
    const wrapper = mount(GuessOverlay)
    await push([
      { seq: 1, kind: 'freebie', guess: 'pony' },
      { seq: 2, kind: 'freebie', guess: 'safe' },
    ])
    expect(wrapper.text()).toBe('')
  })

  it('queues a batch rather than showing only its last entry', async () => {
    const wrapper = mount(GuessOverlay)
    await push([
      { seq: 1, kind: 'wrong', player: 'bob', guess: 'stallion', strike: 1 },
      correct(2, 'mare'),
    ])
    // The wrong guess shows first, even though a later entry arrived with it.
    expect(wrapper.text()).toContain('stallion')

    // A backed-up queue holds each card briefly rather than stacking them.
    await vi.advanceTimersByTimeAsync(700 + 180)
    expect(wrapper.text()).toContain('mare')
  })

  it('does not repeat an elimination that its third strike already showed', async () => {
    const wrapper = mount(GuessOverlay)
    await push([
      { seq: 1, kind: 'wrong', player: 'bob', guess: 'stallion', strike: 3 },
      { seq: 2, kind: 'eliminated', player: 'bob' },
    ])
    expect(wrapper.text()).toContain('stallion')
    expect(wrapper.text()).toContain('eliminated')

    // The pair always arrives together and says one thing; only the strike shows.
    await vi.advanceTimersByTimeAsync(1500 + 180)
    expect(wrapper.text()).toBe('')
  })

  it('clears the picture when the band can hold the card, and never the frame', async () => {
    // jsdom lays nothing out, so the card's height has to be handed over.
    vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockReturnValue(70)
    // `wrapper.element` is the leading comment, so ask for the band itself.
    const band = (wrapper: ReturnType<typeof mount>) => wrapper.get('div').element.style.bottom

    const roomy = mount(GuessOverlay, { props: { pictureBottom: 200 } })
    await push([correct(1)])
    expect(band(roomy)).toBe('130px') // lifted to sit under the picture

    const tight = mount(GuessOverlay, { props: { pictureBottom: 10 } })
    await push([correct(2)])
    // Too shallow to clear the picture, so it rests on the frame's own edge
    // rather than hanging past it, where the frame would clip it away.
    expect(band(tight)).toBe('0px')
  })

  it('renders one X per strike taken, never padded to the limit', async () => {
    const wrapper = mount(GuessOverlay)
    await push([{ seq: 1, kind: 'wrong', player: 'bob', guess: 'stallion', strike: 2 }])
    expect(wrapper.findAll('.strike')).toHaveLength(2)
    expect(wrapper.text()).toContain('strike 2 of 3')
  })

  it('shows an aliased guess as the typed word before the tag it scored', async () => {
    const wrapper = mount(GuessOverlay)
    await push([{ ...correct(1, 'twilight sparkle'), asTyped: 'ts' }])
    // Both are there from the first frame — no reveal to wait through, so a
    // glance at any point in the hold sees that a translation happened.
    expect(wrapper.text()).toContain('ts')
    expect(wrapper.text()).toContain('twilight sparkle')
    expect(wrapper.text()).toContain('→')
  })

  it('shows no typed word when the guess was not translated', async () => {
    const wrapper = mount(GuessOverlay)
    await push([correct(1, 'twilight sparkle')])
    expect(wrapper.text()).toContain('twilight sparkle')
    expect(wrapper.text()).not.toContain('→')
  })

  it('drops the oldest of a burst rather than building a backlog', async () => {
    const wrapper = mount(GuessOverlay)
    await push([
      correct(1, 'alpha'),
      correct(2, 'bravo'),
      correct(3, 'charlie'),
      correct(4, 'delta'),
    ])
    // Queue caps at 3, so the first of four never gets shown.
    expect(wrapper.text()).not.toContain('alpha')
    expect(wrapper.text()).toContain('bravo')
  })

  it('clears the card on a pointer press, without waiting out the hold', async () => {
    const wrapper = mount(GuessOverlay)
    await push([correct(1)])
    expect(wrapper.text()).toContain('mare')

    window.dispatchEvent(new Event('pointerdown'))
    await vi.advanceTimersByTimeAsync(0)
    expect(wrapper.text()).not.toContain('mare')
  })

  it('advances to the queued card on a press, so a burst can be clicked through', async () => {
    const wrapper = mount(GuessOverlay)
    await push([correct(1, 'alpha'), correct(2, 'bravo')])
    expect(wrapper.text()).toContain('alpha')

    window.dispatchEvent(new Event('pointerdown'))
    await vi.advanceTimersByTimeAsync(180)
    expect(wrapper.text()).toContain('bravo')
  })

  it('ignores a press when no card is showing', async () => {
    const wrapper = mount(GuessOverlay)
    window.dispatchEvent(new Event('pointerdown'))
    await vi.advanceTimersByTimeAsync(0)
    // A press before anything lands must not consume the card that follows.
    await push([correct(1)])
    expect(wrapper.text()).toContain('mare')
  })

  it('stops listening once unmounted', async () => {
    const wrapper = mount(GuessOverlay)
    await push([correct(1)])
    wrapper.unmount()
    // Would throw on a dangling listener touching a torn-down component.
    window.dispatchEvent(new Event('pointerdown'))
  })

  it('closes a decided round once its last cards have played', async () => {
    const game = useGameStore()
    mount(GuessOverlay)
    // The shape the server actually sends: the deciding guess and the game over
    // arrive in one batch, so the card must outlive the event that ended it.
    await push([
      { seq: 1, kind: 'wrong', player: 'bob', guess: 'stallion', strike: 3 },
      { seq: 2, kind: 'eliminated', player: 'bob' },
    ])
    game.state.status = 'ending'

    await vi.advanceTimersByTimeAsync(600)
    expect(game.state.status).toBe('ending') // strike card still showing

    await vi.advanceTimersByTimeAsync(1500 + 180)
    expect(game.state.status).toBe('over')
  })

  it('reaches the results early when the last cards are clicked through', async () => {
    const game = useGameStore()
    mount(GuessOverlay)
    await push([{ seq: 1, kind: 'wrong', player: 'bob', guess: 'stallion', strike: 3 }])
    game.state.status = 'ending'

    window.dispatchEvent(new Event('pointerdown'))
    await vi.advanceTimersByTimeAsync(180)
    // No waiting out the hold — dismissing the last card ends the outro.
    expect(game.state.status).toBe('over')
  })

  it('leaves a live round alone when the queue drains', async () => {
    const game = useGameStore()
    game.state.status = 'active'
    mount(GuessOverlay)
    await push([correct(1)])
    await vi.advanceTimersByTimeAsync(1500 + 180)
    // Draining mid-round must not end anything — only an `ending` round closes.
    expect(game.state.status).toBe('active')
  })

  it('rewinds with a new round so the next guesses are not treated as stale', async () => {
    const game = useGameStore()
    const wrapper = mount(GuessOverlay)
    await push([correct(9)])
    await vi.advanceTimersByTimeAsync(1500)

    // A fresh round resets the feed, restarting seq at 1.
    game.state.image = { id: 'next', thumb_url: '', full_url: '' }
    game.state.feed = []
    await vi.advanceTimersByTimeAsync(0)
    await push([correct(1, 'pegasus')])
    expect(wrapper.text()).toContain('pegasus')
  })
})
