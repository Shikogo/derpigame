/**
 * The room's mobile shell — which states run it, and what the sheet does while
 * it's up. Everything about the shell's *shape* is a `max-lg:` class, so the
 * only thing worth asserting here is the marker that turns it on plus the
 * behaviour hanging off it.
 */
import { beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import RoomView from '@/views/RoomView.vue'
import GuessDock from '@/components/GuessDock.vue'
import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'
import { useSessionStore } from '@/stores/session'
import { roomState, roomUser } from '@/test/factories'
import type { GameEvent, Player } from '@/types/wire'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', name: 'home', component: { template: '<div />' } },
    { path: '/room/:code', name: 'room', component: { template: '<div />' } },
  ],
})

// ImageViewer measures its frame; jsdom has no ResizeObserver.
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
} as unknown as typeof ResizeObserver

const ME: Player = { uuid: 'me', name: 'ME', score: 0, wrong_guesses: 0 }
const RIVAL: Player = { uuid: 'rival', name: 'Rival', score: 0, wrong_guesses: 0 }

function openRound(first: Player): GameEvent[] {
  return [
    { type: 'image_started', id: '1', thumb_url: 't', full_url: 'f', source: 'derpibooru' },
    {
      type: 'game_started',
      first_player: first,
      players: [ME, RIVAL],
      tag_count: 1,
      bonus_counts: {},
      freebie_tags: [],
      turn_seconds: 30,
      elimination_threshold: 3,
    },
    { type: 'turn_started', player: first },
  ]
}

const gameOver: GameEvent = {
  type: 'game_over',
  win: true,
  winners: [ME],
  standings: [ME],
  win_counts: [],
  unguessed: {},
}

describe('RoomView — mobile shell', () => {
  let pinia: Pinia

  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('derpigame:uuid', 'me')
    pinia = createPinia()
    setActivePinia(pinia)
    useRoomStore().setRoomState(
      roomState({ in_progress: true, users: [roomUser('me', { name: 'ME', ready: true })] }),
    )
  })

  function mountRoom() {
    return mount(RoomView, {
      props: { code: 'r' },
      global: { plugins: [pinia, router], stubs: { RoundLog: true, ConfettiOverlay: true } },
    })
  }

  const shell = (wrapper: ReturnType<typeof mountRoom>) =>
    wrapper.get('main').attributes('data-mobile-shell')
  /** Everything in the rail belongs to a round, so it comes and goes with one. */
  const rail = (wrapper: ReturnType<typeof mountRoom>) => wrapper.find('aside').exists()

  it('runs only for a live round, not the lobby, the gate or the results', async () => {
    const game = useGameStore()
    const room = useRoomStore()

    room.setRoomState(roomState({ users: [roomUser('me', { name: 'ME', ready: false })] }))
    const wrapper = mountRoom()
    await flushPromises()
    expect(shell(wrapper)).toBeUndefined() // lobby scrolls
    expect(rail(wrapper)).toBe(false)

    room.setRoomState(
      roomState({ in_progress: true, users: [roomUser('me', { name: 'ME', ready: true })] }),
    )
    game.applyEvents(openRound(ME))
    await flushPromises()
    expect(shell(wrapper)).toBeDefined()
    expect(rail(wrapper)).toBe(true)

    // The shell is a fixed box; it has to let go before the results land.
    game.applyEvents([gameOver])
    game.finishRound()
    await flushPromises()
    expect(shell(wrapper)).toBeUndefined()
    expect(rail(wrapper)).toBe(false)
  })

  it('stays off behind the age gate, where there is no picture to keep in view', async () => {
    useRoomStore().setRoomState(
      roomState({
        nsfw: true,
        in_progress: true,
        users: [roomUser('me', { name: 'ME', ready: true })],
      }),
    )
    const wrapper = mountRoom()
    useGameStore().applyEvents(openRound(ME))
    await flushPromises()
    expect(shell(wrapper)).toBeUndefined()

    useSessionStore().acknowledgeNsfw()
    await flushPromises()
    expect(shell(wrapper)).toBeDefined()
  })

  it('clears the sheet off the picture when your turn arrives', async () => {
    const game = useGameStore()
    game.applyEvents(openRound(RIVAL))
    const wrapper = mountRoom()
    await flushPromises()

    const dock = () => wrapper.findComponent(GuessDock)
    await dock().vm.$emit('toggle')
    await flushPromises()
    expect(dock().props('sheetOpen')).toBe(true)

    game.applyEvents([{ type: 'turn_started', player: ME }])
    await flushPromises()
    expect(dock().props('sheetOpen')).toBe(false)
  })
})
