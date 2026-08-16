import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import ConfettiOverlay from '@/components/ConfettiOverlay.vue'

// The library animates a real canvas, which jsdom hasn't got. What's under test
// is the wiring: when shots go up, and how many.
const launch = vi.fn()
const reset = vi.fn()
vi.mock('canvas-confetti', () => ({
  default: { create: () => Object.assign(launch, { reset }) },
}))

beforeEach(() => {
  vi.useFakeTimers()
  launch.mockClear()
  reset.mockClear()
})

afterEach(() => vi.useRealTimers())

/** Let every scheduled shot in the queue fire. */
function playSchedule(): void {
  vi.advanceTimersByTime(3000)
}

describe('ConfettiOverlay', () => {
  it('puts the canvas on <body>, out of reach of a transformed ancestor', () => {
    const wrapper = mount(ConfettiOverlay, { attachTo: document.body })

    // The regression: mounted in place, the panel transition's `translateY`
    // becomes the containing block for `position: fixed` and the canvas is
    // sized to the panel for the length of the cross-fade.
    expect(wrapper.element.querySelector('canvas')).toBeNull()
    expect(document.body.querySelector('canvas')).not.toBeNull()

    wrapper.unmount()
    expect(document.body.querySelector('canvas')).toBeNull()
  })

  it('stays idle without a kind, and celebrates with one', () => {
    mount(ConfettiOverlay)
    playSchedule()
    expect(launch).not.toHaveBeenCalled()

    mount(ConfettiOverlay, { props: { kinds: ['winner'] } })
    playSchedule()
    expect(launch).toHaveBeenCalled()
  })

  it('drops pending shots when it unmounts mid-celebration', () => {
    const wrapper = mount(ConfettiOverlay, { props: { kinds: ['winner', 'sweep'] } })

    vi.advanceTimersByTime(100) // the cannons have gone up, the shells have not
    const fired = launch.mock.calls.length
    wrapper.unmount()
    playSchedule()

    expect(launch.mock.calls.length).toBe(fired)
    expect(reset).toHaveBeenCalled()
  })
})
