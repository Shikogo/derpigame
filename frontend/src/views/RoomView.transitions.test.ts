/**
 * Panel switching with the real `<Transition>` in play.
 *
 * Vue Test Utils stubs transitions by default, which is why a bug that left the
 * results panel blank got through the rest of the suite untouched: every other
 * test renders a stub and never exercises enter/leave at all. These mount with
 * `transition: false` so the real thing runs.
 */
import { beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import RoomView from '@/views/RoomView.vue'
import GameOverPanel from '@/components/GameOverPanel.vue'
import GamePanel from '@/components/GamePanel.vue'
import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'
import { roomState } from '@/test/factories'
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

const openRound: GameEvent[] = [
  { type: 'image_started', id: '1', thumb_url: 't', full_url: 'f', source: 'derpibooru' },
  {
    type: 'game_started',
    first_player: ME,
    players: [ME],
    tag_count: 1,
    bonus_counts: {},
    freebie_tags: [],
    turn_seconds: 30,
    elimination_threshold: 3,
  },
  { type: 'turn_started', player: ME },
]

const gameOver: GameEvent = {
  type: 'game_over',
  win: true,
  winners: [ME],
  standings: [ME],
  unguessed: {},
}

describe('RoomView — panel transitions', () => {
  let pinia: Pinia

  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('derpigame:uuid', 'me')
    pinia = createPinia()
    setActivePinia(pinia)
    useRoomStore().setRoomState(
      roomState({ in_progress: true, users: [{ uuid: 'me', name: 'ME', ready: true }] }),
    )
  })

  function mountRoom() {
    return mount(RoomView, {
      props: { code: 'r' },
      global: {
        plugins: [pinia, router],
        // The point of these tests: exercise the real transition, not a stub.
        // Confetti is stubbed only because jsdom has no canvas to draw on.
        stubs: { ChatPanel: true, GameControls: true, ConfettiOverlay: true, transition: false },
      },
    })
  }

  it('shows the results panel once a finished round concludes', async () => {
    const game = useGameStore()
    game.applyEvents(openRound)
    const wrapper = mountRoom()
    await flushPromises()
    expect(wrapper.findComponent(GamePanel).exists()).toBe(true)

    game.applyEvents([gameOver])
    await flushPromises()
    // Still `ending` — the picture stays up so the last cards can play.
    expect(wrapper.findComponent(GamePanel).exists()).toBe(true)
    expect(wrapper.findComponent(GameOverPanel).exists()).toBe(false)

    game.finishRound()
    await flushPromises()
    // The regression: the panel area must never end up empty. Gating the
    // incoming panel on the outgoing one's transition left nothing on screen.
    expect(wrapper.findComponent(GameOverPanel).exists()).toBe(true)
    expect(wrapper.text()).toContain('You won!')
  })

  it('keeps the picture mounted while the round is ending', async () => {
    const game = useGameStore()
    game.applyEvents(openRound)
    const wrapper = mountRoom()
    await flushPromises()

    game.applyEvents([gameOver])
    await flushPromises()
    // GamePanel keys off having a picture, not off status — swapping its root
    // mid-fade pulls the element out from under the transition animating it.
    expect(wrapper.findComponent(GamePanel).exists()).toBe(true)
    expect(wrapper.text()).not.toContain('A round is already in progress')
  })
})
