import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import RoundStatusStrip from '@/components/RoundStatusStrip.vue'
import { useGameStore } from '@/stores/game'

beforeEach(() => {
  setActivePinia(createPinia())

  const game = useGameStore()
  game.state.goalTagCount = 8
  game.state.goalRemaining = 5
  game.state.bonusCounts = { artist: 2 }
  game.state.bonusTotals = { artist: 3 }
})

describe('RoundStatusStrip', () => {
  it('drops the bonus chips when compact, keeping the turn and the progress', () => {
    const full = mount(RoundStatusStrip)
    expect(full.text()).toContain('artist: 2 left')
    expect(full.text()).toContain('3 / 8')

    // The keyboard is up: the picture needs the chips' height more than the
    // round needs the chips.
    const compact = mount(RoundStatusStrip, { props: { compact: true } })
    expect(compact.text()).not.toContain('artist: 2 left')
    expect(compact.text()).toContain('3 / 8')
    expect(compact.text()).toContain('Waiting…')
  })
})
