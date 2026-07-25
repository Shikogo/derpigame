import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import ConfettiOverlay from '@/components/ConfettiOverlay.vue'
import GameOverPanel from '@/components/GameOverPanel.vue'
import { useGameStore } from '@/stores/game'
import type { GameOverResult } from '@/game/reducer'
import type { Player } from '@/types/wire'

const ME: Player = { uuid: 'me', name: 'Me', score: 5, wrong_guesses: 0 }
const RIVAL: Player = { uuid: 'rival', name: 'Rival', score: 9, wrong_guesses: 1 }

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem('derpigame:uuid', ME.uuid)
  setActivePinia(createPinia())
})

/** Mount the results screen on a finished round with the given outcome. */
function mountResult(over: GameOverResult) {
  const game = useGameStore()
  game.state.status = 'over'
  game.state.over = over
  // jsdom has no canvas; the panel's job here is deciding whether to mount it.
  return mount(GameOverPanel, { global: { stubs: { ConfettiOverlay: true } } })
}

/** What the panel asks for: the cannons, the fireworks, both, or nothing. */
function celebration(over: GameOverResult): string[] {
  const overlay = mountResult(over).findComponent(ConfettiOverlay)
  return overlay.exists() ? [...(overlay.props('kinds') as string[])] : []
}

describe('GameOverPanel celebrations', () => {
  it('sends the cannons to the winner only', () => {
    const won = { win: false, winners: [ME], standings: [ME, RIVAL] }

    expect(celebration(won)).toEqual(['winner'])
    expect(celebration({ ...won, winners: [RIVAL] })).toEqual([])
  })

  it('celebrates a clean sweep for everyone, and stacks it on a win', () => {
    const sweptByRival = { win: true, winners: [RIVAL], standings: [RIVAL, ME] }

    // Lost the round the room swept: the fireworks are still yours to watch.
    expect(celebration(sweptByRival)).toEqual(['sweep'])
    expect(celebration({ ...sweptByRival, winners: [ME] })).toEqual(['winner', 'sweep'])
    expect(mountResult(sweptByRival).text()).toContain('Clean sweep')
  })

  it('stays quiet for an aborted round', () => {
    const game = useGameStore()
    game.state.status = 'aborted'
    game.state.over = { win: true, winners: [ME], standings: [ME] }

    const wrapper = mount(GameOverPanel, { global: { stubs: { ConfettiOverlay: true } } })

    expect(wrapper.findComponent(ConfettiOverlay).exists()).toBe(false)
    expect(wrapper.text()).toContain('Round aborted')
  })
})
