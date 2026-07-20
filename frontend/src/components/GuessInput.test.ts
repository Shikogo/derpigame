import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import GuessInput from '@/components/GuessInput.vue'
import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'
import { useSessionStore } from '@/stores/session'

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('GuessInput', () => {
  it('is disabled when it is not your turn', () => {
    // No active player set, so isMyTurn is false.
    const wrapper = mount(GuessInput)

    const input = wrapper.find('input').element as HTMLInputElement
    const button = wrapper.find('button').element as HTMLButtonElement
    expect(input.disabled).toBe(true)
    expect(button.disabled).toBe(true)
    expect(input.placeholder).toBe('Wait for your turn')
  })

  it('enables the box on your turn and submits the trimmed guess', async () => {
    const session = useSessionStore()
    const game = useGameStore()
    game.state.activePlayerUuid = session.uuid // now isMyTurn

    const room = useRoomStore()
    const guess = vi.spyOn(room, 'submitGuess').mockResolvedValue({ ok: true })

    const wrapper = mount(GuessInput)
    await nextTick()

    expect((wrapper.find('input').element as HTMLInputElement).disabled).toBe(false)
    // Button stays disabled until there's a non-empty guess.
    expect((wrapper.find('button').element as HTMLButtonElement).disabled).toBe(true)

    await wrapper.find('input').setValue('  mare  ')
    expect((wrapper.find('button').element as HTMLButtonElement).disabled).toBe(false)

    await wrapper.find('form').trigger('submit')

    expect(guess).toHaveBeenCalledWith('mare')
    // The box clears after submitting.
    expect((wrapper.find('input').element as HTMLInputElement).value).toBe('')
  })

  it('focuses the box when your turn begins', async () => {
    const session = useSessionStore()
    const game = useGameStore()

    const wrapper = mount(GuessInput, { attachTo: document.body })
    const input = wrapper.find('input').element as HTMLInputElement
    expect(document.activeElement).not.toBe(input)

    game.state.activePlayerUuid = session.uuid // now isMyTurn
    await nextTick() // watcher enables the box
    await nextTick() // ...then focuses it

    expect(document.activeElement).toBe(input)
    wrapper.unmount()
  })

  it('focuses the box when mounted already on your turn (starting player)', async () => {
    const session = useSessionStore()
    const game = useGameStore()
    game.state.activePlayerUuid = session.uuid // already isMyTurn before mount

    const wrapper = mount(GuessInput, { attachTo: document.body })
    await nextTick() // immediate watcher focuses after the ref is bound

    expect(document.activeElement).toBe(wrapper.find('input').element)
    wrapper.unmount()
  })

  it('spins the button while a guess is in flight, leaving the box usable', async () => {
    const session = useSessionStore()
    const game = useGameStore()
    game.state.activePlayerUuid = session.uuid

    const room = useRoomStore()
    const wrapper = mount(GuessInput)

    expect(wrapper.find('button span.animate-spin').exists()).toBe(false)

    room.guessing = true
    await nextTick()

    expect(wrapper.find('button span.animate-spin').exists()).toBe(true)
    expect((wrapper.find('button').element as HTMLButtonElement).disabled).toBe(true)
    // The box stays enabled so it keeps focus for the next guess this turn.
    expect((wrapper.find('input').element as HTMLInputElement).disabled).toBe(false)
  })

  it('does not submit while a guess is already in flight', async () => {
    const session = useSessionStore()
    const game = useGameStore()
    game.state.activePlayerUuid = session.uuid

    const room = useRoomStore()
    room.guessing = true
    const guess = vi.spyOn(room, 'submitGuess').mockResolvedValue({ ok: true })

    const wrapper = mount(GuessInput)
    await wrapper.find('input').setValue('mare')
    await wrapper.find('form').trigger('submit')

    expect(guess).not.toHaveBeenCalled()
  })

  it('does not submit an empty or whitespace-only guess', async () => {
    const session = useSessionStore()
    const game = useGameStore()
    game.state.activePlayerUuid = session.uuid

    const room = useRoomStore()
    const guess = vi.spyOn(room, 'submitGuess').mockResolvedValue({ ok: true })

    const wrapper = mount(GuessInput)
    await wrapper.find('input').setValue('   ')
    await wrapper.find('form').trigger('submit')

    expect(guess).not.toHaveBeenCalled()
  })
})
