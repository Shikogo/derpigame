import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import GuessDock from '@/components/GuessDock.vue'
import GuessInput from '@/components/GuessInput.vue'
import { useGameStore } from '@/stores/game'
import type { Player } from '@/types/wire'

const RIVAL: Player = { uuid: 'rival', name: 'Rival', score: 0, wrong_guesses: 0 }

beforeEach(() => {
  setActivePinia(createPinia())
})

function mountDock(props: Partial<{ sheetOpen: boolean }> = {}) {
  return mount(GuessDock, { props: { sheetOpen: false, ...props } })
}

describe('GuessDock', () => {
  it('offers the box to a player and a note to a spectator', async () => {
    const game = useGameStore()
    expect(mountDock().findComponent(GuessInput).exists()).toBe(true)

    // A live round whose roster doesn't include you: you're watching.
    game.state.status = 'active'
    game.state.players = { [RIVAL.uuid]: RIVAL }
    const watching = mountDock()

    expect(watching.findComponent(GuessInput).exists()).toBe(false)
    expect(watching.text()).toContain("You're spectating")
  })

  it('toggles the sheet and says which way it goes', async () => {
    const wrapper = mountDock({ sheetOpen: false })
    // Not `get('button')` — the guess box has one, and it comes first.
    const handle = wrapper.get('[aria-controls="round-sheet"]')

    expect(handle.attributes('aria-expanded')).toBe('false')
    await handle.trigger('click')
    expect(wrapper.emitted('toggle')).toHaveLength(1)

    await wrapper.setProps({ sheetOpen: true })
    expect(handle.attributes('aria-expanded')).toBe('true')
    expect(handle.attributes('aria-label')).toContain('Hide')
  })
})
