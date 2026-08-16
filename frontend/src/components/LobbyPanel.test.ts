import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'

import LobbyPanel from '@/components/LobbyPanel.vue'
import { MASKED_CODE } from '@/lib/roomCode'
import { usePreferencesStore } from '@/stores/preferences'
import { useRoomStore } from '@/stores/room'
import { roomState } from '@/test/factories'

const stubs = { UserList: true, ReadyBar: true, RoomSettings: true, HistoryPanel: true }

const writeText = vi.fn().mockResolvedValue(undefined)

describe('LobbyPanel — invite link', () => {
  let pinia: Pinia

  beforeEach(() => {
    localStorage.clear()
    writeText.mockClear()
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    pinia = createPinia()
    setActivePinia(pinia)
    useRoomStore().setRoomState(roomState())
  })

  function mountLobby() {
    return mount(LobbyPanel, { global: { plugins: [pinia], stubs } })
  }

  it('masks the shown link in streamer mode but still copies the real one', async () => {
    const real = `${location.origin}/room/r`
    const wrapper = mountLobby()
    expect(wrapper.get('input').element.value).toBe(real)

    usePreferencesStore().setStreamerMode(true)
    await wrapper.vm.$nextTick()
    expect(wrapper.get('input').element.value).toBe(`${location.origin}/room/${MASKED_CODE}`)

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Copy')!
      .trigger('click')
    expect(writeText).toHaveBeenCalledWith(real)
  })
})
