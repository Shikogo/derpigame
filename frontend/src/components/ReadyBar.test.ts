import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import ReadyBar from '@/components/ReadyBar.vue'
import { emitAck } from '@/socket/client'
import { useRoomStore } from '@/stores/room'
import { roomState, roomUser } from '@/test/factories'

vi.mock('@/socket/client', () => ({ emitAck: vi.fn() }))

const ME = 'me'

beforeEach(() => {
  localStorage.clear()
  localStorage.setItem('derpigame:uuid', ME)
  setActivePinia(createPinia())
  vi.mocked(emitAck).mockReset()
  vi.mocked(emitAck).mockResolvedValue({ ok: true })
})

/** Mount the bar in a room where I'm ready or not, with one other member. */
function mountBar(ready: boolean, props = {}, rivalReady = false) {
  useRoomStore().setRoomState(
    roomState({
      users: [
        roomUser(ME, { name: 'Me', ready }),
        roomUser('rival', { name: 'Rival', ready: rivalReady }),
      ],
    }),
  )
  return mount(ReadyBar, { props })
}

describe('ReadyBar', () => {
  it('gates start on your own ready, and toggles it in place', async () => {
    const notReady = mountBar(false)
    const [readyButton, startButton] = notReady.findAll('button')

    expect(startButton.attributes('disabled')).toBeDefined()
    expect(readyButton.text()).toBe('Ready up')

    await readyButton.trigger('click')
    expect(emitAck).toHaveBeenCalledWith('set_ready', { ready: true })

    const ready = mountBar(true)
    expect(ready.findAll('button')[1].attributes('disabled')).toBeUndefined()
    expect(ready.findAll('button')[0].text()).toBe('Ready ✓')
    // Readying up un-readies on a second press rather than sticking.
    await ready.findAll('button')[0].trigger('click')
    expect(emitAck).toHaveBeenLastCalledWith('set_ready', { ready: false })
  })

  it('says what is holding the start up, then who is in for the round', () => {
    expect(mountBar(false).text()).toContain('Ready up to start · 0 of 2 ready')
    expect(mountBar(true).text()).toContain('1 of 2 ready · Rival will spectate')
  })

  it('haloes the start button only once the room is waiting on nobody', () => {
    expect(mountBar(true).findAll('button')[1].classes()).not.toContain('all-ready')
    expect(mountBar(true, {}, true).findAll('button')[1].classes()).toContain('all-ready')
  })

  it('offers the way back only where the results screen asks for it', async () => {
    expect(mountBar(true).text()).not.toContain('Back to lobby')

    const results = mountBar(true, { startLabel: 'Start next round', showBack: true })
    expect(results.findAll('button')[1].text()).toBe('Start next round')

    const back = results.findAll('button')[2]
    expect(back.text()).toContain('Back to lobby')
    await back.trigger('click')
    expect(results.emitted('back')).toHaveLength(1)
  })
})
