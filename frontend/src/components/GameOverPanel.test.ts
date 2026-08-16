import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import ConfettiOverlay from '@/components/ConfettiOverlay.vue'
import GameOverPanel from '@/components/GameOverPanel.vue'
import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'
import { roomState } from '@/test/factories'
import type { GameOverResult } from '@/game/reducer'
import type { Player } from '@/types/wire'

const ME: Player = { uuid: 'me', name: 'Me', score: 5, wrong_guesses: 0 }
const RIVAL: Player = { uuid: 'rival', name: 'Rival', score: 9, wrong_guesses: 1 }

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem('derpigame:uuid', ME.uuid)
  setActivePinia(createPinia())
})

/** An outcome to mount; the win tally defaults to empty where it isn't the point. */
type Outcome = Omit<GameOverResult, 'winCounts'> & Partial<Pick<GameOverResult, 'winCounts'>>

/** Mount the results screen on a finished round with the given outcome. */
function mountResult(over: Outcome) {
  const game = useGameStore()
  game.state.status = 'over'
  game.state.over = { winCounts: [], ...over }
  // jsdom has no canvas; the panel's job here is deciding whether to mount it.
  return mount(GameOverPanel, {
    props: { arrivals: 0 },
    global: { stubs: { ConfettiOverlay: true } },
  })
}

/** What the panel asks for once it has arrived: cannons, fireworks, both, none. */
async function celebration(over: Outcome): Promise<string[]> {
  const wrapper = mountResult(over)
  await wrapper.setProps({ arrivals: 1 })
  const overlay = wrapper.findComponent(ConfettiOverlay)
  return overlay.exists() ? [...(overlay.props('kinds') as string[])] : []
}

describe('GameOverPanel celebrations', () => {
  it('sends the cannons to the winner only', async () => {
    const won = { win: false, winners: [ME], standings: [ME, RIVAL] }

    expect(await celebration(won)).toEqual(['winner'])
    expect(await celebration({ ...won, winners: [RIVAL] })).toEqual([])
  })

  it('celebrates a clean sweep for everyone, and stacks it on a win', async () => {
    const sweptByRival = { win: true, winners: [RIVAL], standings: [RIVAL, ME] }

    // Lost the round the room swept: the fireworks are still yours to watch.
    expect(await celebration(sweptByRival)).toEqual(['sweep'])
    expect(await celebration({ ...sweptByRival, winners: [ME] })).toEqual(['winner', 'sweep'])
    expect(mountResult(sweptByRival).text()).toContain('Clean sweep')
  })

  it('holds the cannons until the panel has arrived', async () => {
    const wrapper = mountResult({ win: false, winners: [ME], standings: [ME] })
    expect(wrapper.findComponent(ConfettiOverlay).exists()).toBe(false)

    await wrapper.setProps({ arrivals: 1 })
    expect(wrapper.findComponent(ConfettiOverlay).exists()).toBe(true)
  })

  it('stays quiet for an aborted round', () => {
    const game = useGameStore()
    game.state.status = 'aborted'
    game.state.over = { win: true, winners: [ME], standings: [ME], winCounts: [] }

    const wrapper = mount(GameOverPanel, { global: { stubs: { ConfettiOverlay: true } } })

    expect(wrapper.findComponent(ConfettiOverlay).exists()).toBe(false)
    expect(wrapper.text()).toContain('Round aborted')
  })
})

describe('GameOverPanel heading', () => {
  const THIRD: Player = { uuid: 'third', name: 'Third', score: 9, wrong_guesses: 0 }

  it('names every winner of a tie, with you at the front', () => {
    const tie = { win: false, winners: [RIVAL, ME, THIRD], standings: [RIVAL, ME, THIRD] }

    expect(mountResult(tie).text()).toContain('You, Rival, and Third won! 🎉')
    // Same tie without you: still everyone, no second person, no cheer.
    expect(mountResult({ ...tie, winners: [RIVAL, THIRD] }).text()).toContain(
      'Rival and Third won!',
    )
  })

  it('keeps a solo win to one name', () => {
    expect(mountResult({ win: false, winners: [ME], standings: [ME] }).text()).toContain(
      'You won! 🎉',
    )
    expect(mountResult({ win: false, winners: [], standings: [ME] }).text()).toContain('Round over')
  })
})

describe('GameOverPanel standings', () => {
  it('shows each winner their room tally, and nothing for the winless', () => {
    const wrapper = mountResult({
      win: false,
      winners: [RIVAL],
      standings: [RIVAL, ME],
      winCounts: [{ uuid: RIVAL.uuid, name: RIVAL.name, wins: 3 }],
    })

    const rows = wrapper.findAll('ol li')
    expect(rows[0].text()).toContain('🏆 3')
    expect(rows[1].text()).not.toContain('🏆')
  })
})

describe('GameOverPanel attribution', () => {
  it("names the booru the round came from, not the room's current one", () => {
    useRoomStore().setRoomState(roomState({ source: 'derpibooru' }))
    const game = useGameStore()
    game.state.source = 'furbooru'
    game.state.reveal = { artists: [], source_url: null, page_url: 'https://furbooru.org/1' }

    const link = mountResult({ win: false, winners: [ME], standings: [ME] }).get(
      'a[href="https://furbooru.org/1"]',
    )

    expect(link.text()).toBe('on Furbooru')
  })
})
