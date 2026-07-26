import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import Scoreboard from '@/components/Scoreboard.vue'
import { useGameStore } from '@/stores/game'
import type { Player } from '@/types/wire'

beforeEach(() => {
  setActivePinia(createPinia())
})

const player = (uuid: string, over: Partial<Player> = {}): Player => ({
  uuid,
  name: uuid,
  score: 0,
  wrong_guesses: 0,
  ...over,
})

describe('Scoreboard', () => {
  it('draws the whole strike allowance per row, filling the spent ones', () => {
    const game = useGameStore()
    game.state.strikeLimit = 4
    game.state.players = {
      clean: player('clean', { score: 5 }),
      out: player('out', { score: 2, wrong_guesses: 4 }),
    }
    game.state.eliminated = ['out']

    const wrapper = mount(Scoreboard)
    const [clean, out] = wrapper.findAll('li')

    // Same number of crosses either way — that's what holds the score column.
    expect(clean.findAll('svg')).toHaveLength(4)
    expect(out.findAll('svg')).toHaveLength(4)

    const filled = (row: (typeof clean)['element']) =>
      [...row.querySelectorAll('svg')].filter((s) => s.classList.contains('text-wrong')).length
    expect(filled(clean.element)).toBe(0)
    expect(filled(out.element)).toBe(4)

    expect(clean.find('[role="img"]').attributes('aria-label')).toBe('0 of 4 strikes')
    expect(out.find('[role="img"]').attributes('aria-label')).toBe('4 of 4 strikes')
  })
})
