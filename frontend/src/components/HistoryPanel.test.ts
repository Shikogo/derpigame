import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'

import HistoryPanel from '@/components/HistoryPanel.vue'
import AgeGate from '@/components/AgeGate.vue'
import { useRoomStore } from '@/stores/room'
import { useSessionStore } from '@/stores/session'
import type { RoomState, RoundRecord } from '@/types/wire'

const round: RoundRecord = {
  page_url: 'https://derpi/1',
  source_url: null,
  thumb_url: 't.jpg',
  artists: [],
  win: true,
  aborted: false,
  winners: [{ uuid: 'a', name: 'A', score: 1, wrong_guesses: 0 }],
  standings: [],
}

function roomState(over: Partial<RoomState> = {}): RoomState {
  return { room: 'r', query: [], nsfw: true, in_progress: false, turn_seconds: 30, users: [], history: [round], win_counts: [], ...over }
}

describe('HistoryPanel — NSFW thumbnails', () => {
  let pinia: Pinia

  beforeEach(() => {
    localStorage.clear()
    pinia = createPinia()
    setActivePinia(pinia)
    HTMLDialogElement.prototype.showModal = vi.fn()
    HTMLDialogElement.prototype.close = vi.fn()
  })

  const mountPanel = () => mount(HistoryPanel, { global: { plugins: [pinia] } })

  it('blurs thumbnails in an NSFW room until attested', () => {
    useRoomStore().setRoomState(roomState())
    const wrapper = mountPanel()
    expect(wrapper.find('img').classes()).toContain('blur-md')
  })

  it('a thumbnail click opens the gate instead of silently revealing', async () => {
    useRoomStore().setRoomState(roomState())
    const session = useSessionStore()
    const wrapper = mountPanel()

    await wrapper.find('a').trigger('click')

    expect(session.nsfwAck).toBe(false) // no bypass — not acknowledged yet
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalled()
  })

  it('confirming in the gate attests and unblurs', async () => {
    useRoomStore().setRoomState(roomState())
    const session = useSessionStore()
    const wrapper = mountPanel()

    await wrapper.findComponent(AgeGate).get('button:last-of-type').trigger('click')

    expect(session.nsfwAck).toBe(true)
    expect(wrapper.find('img').classes()).not.toContain('blur-md')
  })

  it('does not blur or gate in an SFW room', async () => {
    useRoomStore().setRoomState(roomState({ nsfw: false }))
    const wrapper = mountPanel()

    expect(wrapper.find('img').classes()).not.toContain('blur-md')
    await wrapper.find('a').trigger('click')
    expect(HTMLDialogElement.prototype.showModal).not.toHaveBeenCalled()
  })
})

describe('HistoryPanel — win coloring', () => {
  let pinia: Pinia

  beforeEach(() => {
    localStorage.clear()
    pinia = createPinia()
    setActivePinia(pinia)
  })

  const mountPanel = () => mount(HistoryPanel, { global: { plugins: [pinia] } })

  it('colors the outcome green only when you were a winner', () => {
    const you: RoundRecord = { ...round, winners: [{ uuid: 'me', name: 'Me', score: 1, wrong_guesses: 0 }] }
    useSessionStore().uuid = 'me'
    useRoomStore().setRoomState(roomState({ nsfw: false, history: [you] }))

    const outcome = mountPanel().find('.min-w-0 span')
    expect(outcome.classes()).toContain('text-correct')
    expect(outcome.classes()).not.toContain('text-ink-muted')
  })

  it("uses a neutral color when someone else won", () => {
    useSessionStore().uuid = 'me' // round's winner is uuid 'a', not us
    useRoomStore().setRoomState(roomState({ nsfw: false }))

    const outcome = mountPanel().find('.min-w-0 span')
    expect(outcome.classes()).toContain('text-ink-muted')
    expect(outcome.classes()).not.toContain('text-correct')
  })
})
