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
