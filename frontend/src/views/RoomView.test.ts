import { beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import RoomView from '@/views/RoomView.vue'
import AgeGate from '@/components/AgeGate.vue'
import GamePanel from '@/components/GamePanel.vue'
import { MASKED_CODE, rememberRoom } from '@/lib/roomCode'
import { usePreferencesStore } from '@/stores/preferences'
import { useRoomStore } from '@/stores/room'
import { useSessionStore } from '@/stores/session'
import { roomState as baseRoomState, roomUser } from '@/test/factories'
import type { RoomState } from '@/types/wire'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', name: 'home', component: { template: '<div />' } },
    { path: '/room/:code?', name: 'room', component: { template: '<div />' } },
  ],
})

// Stub the panels so the test only exercises which one RoomView chooses.
const stubs = {
  GamePanel: true,
  GameOverPanel: true,
  LobbyPanel: true,
  RoundStatusStrip: true,
  GuessDock: true,
  RoundLog: true,
}

/** These tests are about the age gate over a live game, so default to both. */
function roomState(over: Partial<RoomState> = {}): RoomState {
  return baseRoomState({
    nsfw: true,
    in_progress: true,
    users: [roomUser('me', { name: 'ME', ready: true })],
    ...over,
  })
}

describe('RoomView — NSFW age gate', () => {
  let pinia: Pinia

  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('derpigame:uuid', 'me') // makes room.me / isMember resolve
    pinia = createPinia()
    setActivePinia(pinia)
  })

  function mountRoom() {
    return mount(RoomView, { props: { code: 'r' }, global: { plugins: [pinia, router], stubs } })
  }

  it('gates the live game behind the age gate when NSFW and not attested', async () => {
    useRoomStore().setRoomState(roomState())
    const wrapper = mountRoom()
    await flushPromises()

    expect(wrapper.findComponent(AgeGate).exists()).toBe(true)
    expect(wrapper.findComponent(GamePanel).exists()).toBe(false)
  })

  it('shows the game (no gate) once attested', async () => {
    useSessionStore().acknowledgeNsfw()
    useRoomStore().setRoomState(roomState())
    const wrapper = mountRoom()
    await flushPromises()

    expect(wrapper.findComponent(AgeGate).exists()).toBe(false)
    expect(wrapper.findComponent(GamePanel).exists()).toBe(true)
  })

  it('does not gate an SFW room', async () => {
    useRoomStore().setRoomState(roomState({ nsfw: false }))
    const wrapper = mountRoom()
    await flushPromises()

    expect(wrapper.findComponent(AgeGate).exists()).toBe(false)
    expect(wrapper.findComponent(GamePanel).exists()).toBe(true)
  })

  it('confirming attests and swaps the gate for the game', async () => {
    useRoomStore().setRoomState(roomState())
    const wrapper = mountRoom()
    await flushPromises()

    await wrapper.findComponent(AgeGate).get('button:last-of-type').trigger('click')
    await flushPromises()

    expect(useSessionStore().nsfwAck).toBe(true)
    expect(wrapper.findComponent(AgeGate).exists()).toBe(false)
    expect(wrapper.findComponent(GamePanel).exists()).toBe(true)
  })
})

describe('RoomView — streamer mode', () => {
  let pinia: Pinia

  beforeEach(async () => {
    localStorage.clear()
    sessionStorage.clear()
    localStorage.setItem('derpigame:uuid', 'me')
    pinia = createPinia()
    setActivePinia(pinia)
    await router.replace('/room/r')
  })

  function mountRoom(props: { code?: string } = { code: 'r' }) {
    useRoomStore().setRoomState(baseRoomState({ users: [roomUser('me')] }))
    return mount(RoomView, { props, global: { plugins: [pinia, router], stubs } })
  }

  it('masks the code and drops it from the URL, and puts both back', async () => {
    const prefs = usePreferencesStore()
    const wrapper = mountRoom()
    await flushPromises()

    expect(wrapper.get('.pill').text()).toBe('r')
    expect(router.currentRoute.value.path).toBe('/room/r')

    prefs.toggle()
    await flushPromises()
    expect(wrapper.get('.pill').text()).toBe(MASKED_CODE)
    expect(router.currentRoute.value.path).toBe('/room')

    prefs.toggle()
    await flushPromises()
    expect(wrapper.get('.pill').text()).toBe('r')
    expect(router.currentRoute.value.path).toBe('/room/r')
  })

  it('takes the code from the tab when the URL has none, and goes home without one', async () => {
    rememberRoom('r')
    const wrapper = mountRoom({})
    await flushPromises()
    expect(wrapper.get('.pill').text()).toBe('r')

    sessionStorage.clear()
    setActivePinia((pinia = createPinia()))
    mountRoom({})
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('home')
  })
})
