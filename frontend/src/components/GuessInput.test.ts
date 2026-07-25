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
  it('stays typeable off your turn but refuses to send', async () => {
    // No active player set, so isMyTurn is false.
    const room = useRoomStore()
    const guess = vi.spyOn(room, 'submitGuess').mockResolvedValue({ ok: true })

    const wrapper = mount(GuessInput)
    const input = wrapper.find('input')

    expect((input.element as HTMLInputElement).disabled).toBe(false)
    expect((input.element as HTMLInputElement).placeholder).toBe('Type ahead for your turn…')

    await input.setValue('mare')
    expect((wrapper.find('button').element as HTMLButtonElement).disabled).toBe(true)

    await wrapper.find('form').trigger('submit')
    expect(guess).not.toHaveBeenCalled()
    // Enter off-turn is a no-op — it must not eat what you typed ahead.
    expect((input.element as HTMLInputElement).value).toBe('mare')
  })

  it('sends the guess typed ahead once your turn arrives', async () => {
    const session = useSessionStore()
    const game = useGameStore()
    const room = useRoomStore()
    const guess = vi.spyOn(room, 'submitGuess').mockResolvedValue({ ok: true })

    const wrapper = mount(GuessInput)
    await wrapper.find('input').setValue('  mare  ')

    game.state.activePlayerUuid = session.uuid // now isMyTurn
    await nextTick()

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

  it('hands focus back to the box after the Guess button sends', async () => {
    const session = useSessionStore()
    const game = useGameStore()
    game.state.activePlayerUuid = session.uuid
    const room = useRoomStore()
    const guess = vi.spyOn(room, 'submitGuess').mockResolvedValue({ ok: true })

    const wrapper = mount(GuessInput, { attachTo: document.body })
    await wrapper.find('input').setValue('mare')

    const button = wrapper.find('button')
    ;(button.element as HTMLButtonElement).focus() // as a real click would
    await button.trigger('click')

    expect(guess).toHaveBeenCalledWith('mare') // the click really did send
    expect(document.activeElement).toBe(wrapper.find('input').element)
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
