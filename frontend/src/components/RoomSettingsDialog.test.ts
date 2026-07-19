import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import RoomSettingsDialog from '@/components/RoomSettingsDialog.vue'
import { useRoomStore } from '@/stores/room'
import { roomState } from '@/test/factories'

// jsdom has no real <dialog> modal behaviour; stub the methods the component calls.
beforeEach(() => {
  setActivePinia(createPinia())
  HTMLDialogElement.prototype.showModal = vi.fn()
  HTMLDialogElement.prototype.close = vi.fn()
})

describe('RoomSettingsDialog', () => {
  it('seeds the editor from the current snapshot each time it opens', async () => {
    const room = useRoomStore()
    room.setRoomState(roomState({ query: ['safe', 'pony'], nsfw: true, turn_seconds: 45 }))

    const wrapper = mount(RoomSettingsDialog)
    ;(wrapper.vm as unknown as { open: () => void }).open()
    await nextTick()

    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('safe, pony')
    expect((wrapper.find('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(true)
    expect((wrapper.find('input[type="number"]').element as HTMLInputElement).value).toBe('45')
  })

  it('applying broadcasts the edited settings via configureRoom', async () => {
    const room = useRoomStore()
    room.setRoomState(roomState())
    const configure = vi.spyOn(room, 'configureRoom').mockResolvedValue({ ok: true })

    const wrapper = mount(RoomSettingsDialog)
    ;(wrapper.vm as unknown as { open: () => void }).open()
    await nextTick()

    await wrapper.find('textarea').setValue('cute, mare')
    await wrapper.find('input[type="checkbox"]').setValue(true)
    await wrapper.find('input[type="number"]').setValue('60')
    await wrapper.find('form').trigger('submit')

    expect(configure).toHaveBeenCalledWith({ query: 'cute, mare', nsfw: true, turn_seconds: 60 })
  })

  it('does not broadcast when cancelled', async () => {
    const room = useRoomStore()
    room.setRoomState(roomState())
    const configure = vi.spyOn(room, 'configureRoom').mockResolvedValue({ ok: true })

    const wrapper = mount(RoomSettingsDialog)
    ;(wrapper.vm as unknown as { open: () => void }).open()
    await nextTick()

    await wrapper.find('textarea').setValue('discarded')
    await wrapper.findAll('button').find((b) => b.text() === 'Cancel')!.trigger('click')

    expect(configure).not.toHaveBeenCalled()
  })
})
