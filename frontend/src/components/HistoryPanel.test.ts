import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'

import HistoryPanel from '@/components/HistoryPanel.vue'
import AgeGate from '@/components/AgeGate.vue'
import { useRoomStore } from '@/stores/room'
import { useSessionStore } from '@/stores/session'
import { roomState as baseRoomState } from '@/test/factories'
import type { RoomState, RoundRecord } from '@/types/wire'

const round: RoundRecord = {
  page_url: 'https://derpi/1',
  source_url: null,
  thumb_url: 't.jpg',
  nsfw: false,
  artists: [],
  win: true,
  aborted: false,
  winners: [{ uuid: 'a', name: 'A', score: 1, wrong_guesses: 0 }],
  standings: [],
}
const nsfwRound: RoundRecord = { ...round, nsfw: true }

/** These tests are about thumbnails, so default to an NSFW room with a round. */
function roomState(over: Partial<RoomState> = {}): RoomState {
  return baseRoomState({ nsfw: true, history: [round], ...over })
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

  it('blurs an NSFW round until attested', () => {
    useRoomStore().setRoomState(roomState({ history: [nsfwRound] }))
    const wrapper = mountPanel()
    expect(wrapper.find('img').classes()).toContain('blur-md')
  })

  it('keeps an NSFW round gated even after the room is set back to SFW', () => {
    // The regression: blur must follow the round's own flag, not the room's.
    useRoomStore().setRoomState(roomState({ nsfw: false, history: [nsfwRound] }))
    const wrapper = mountPanel()
    expect(wrapper.find('img').classes()).toContain('blur-md')
  })

  it('a blurred-thumbnail click opens the gate instead of silently revealing', async () => {
    useRoomStore().setRoomState(roomState({ history: [nsfwRound] }))
    const session = useSessionStore()
    const wrapper = mountPanel()

    await wrapper.find('button').trigger('click') // the blurred thumbnail

    expect(session.nsfwAck).toBe(false) // no bypass — not acknowledged yet
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalled()
  })

  it('gates the outbound links until attested', async () => {
    useRoomStore().setRoomState(roomState({ history: [nsfwRound] }))
    const session = useSessionStore()
    const wrapper = mountPanel()

    await wrapper.find('li a').trigger('click') // the Derpibooru link

    expect(session.nsfwAck).toBe(false)
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalled() // opened the gate, didn't navigate
  })

  it('confirming in the gate attests and unblurs', async () => {
    useRoomStore().setRoomState(roomState({ history: [nsfwRound] }))
    const session = useSessionStore()
    const wrapper = mountPanel()

    await wrapper.findComponent(AgeGate).get('button:last-of-type').trigger('click')

    expect(session.nsfwAck).toBe(true)
    expect(wrapper.find('img').classes()).not.toContain('blur-md')
  })

  it('does not blur or gate an SFW round', async () => {
    useRoomStore().setRoomState(roomState({ history: [round] }))
    const wrapper = mountPanel()

    expect(wrapper.find('img').classes()).not.toContain('blur-md')
    await wrapper.find('li a').trigger('click')
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

describe('HistoryPanel — round links', () => {
  let pinia: Pinia

  beforeEach(() => {
    localStorage.clear()
    pinia = createPinia()
    setActivePinia(pinia)
  })

  const mountPanel = () => mount(HistoryPanel, { global: { plugins: [pinia] } })

  it('surfaces a derpibooru link and, when present, a source link', () => {
    const sourced: RoundRecord = { ...round, source_url: 'https://artist.example/art' }
    useRoomStore().setRoomState(roomState({ nsfw: false, history: [sourced] }))

    const links = mountPanel().findAll('li a')
    expect(links.map((l) => l.text())).toEqual(['Derpibooru', 'Source'])
    expect(links[0].attributes('href')).toBe(round.page_url)
    expect(links[1].attributes('href')).toBe('https://artist.example/art')
  })

  it('omits the source link when the round has no source', () => {
    useRoomStore().setRoomState(roomState({ nsfw: false })) // round.source_url is null
    const links = mountPanel().findAll('li a')
    expect(links).toHaveLength(1)
    expect(links[0].text()).toBe('Derpibooru')
  })
})
