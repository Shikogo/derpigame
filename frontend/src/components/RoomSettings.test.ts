import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import RoomSettings from '@/components/RoomSettings.vue'
import { useRoomStore } from '@/stores/room'
import { useSessionStore } from '@/stores/session'
import { roomState } from '@/test/factories'
import type { RoomState } from '@/types/wire'

// jsdom has no real <dialog> modal behaviour; stub the methods the component
// calls, and fire `close` by hand where the browser would.
beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  HTMLDialogElement.prototype.showModal = vi.fn()
  HTMLDialogElement.prototype.close = vi.fn()
})

/** Seed the store and mount — the state every test starts from. */
function mountWith(over: Partial<RoomState> = {}) {
  const room = useRoomStore()
  room.setRoomState(roomState(over))
  const configure = vi.spyOn(room, 'configureRoom').mockResolvedValue({ ok: true })

  return { wrapper: mount(RoomSettings), room, configure }
}

const value = (wrapper: VueWrapper, name: string) =>
  (wrapper.find(`[name="${name}"]`).element as HTMLInputElement | HTMLSelectElement).value

const checked = (wrapper: VueWrapper, name: string) =>
  (wrapper.find(`[name="${name}"]`).element as HTMLInputElement).checked

/**
 * Type without committing. `setValue` fires `change` as well as `input`, which
 * is the browser's "you're done"; mid-edit is `input` alone.
 */
async function type(wrapper: VueWrapper, name: string, text: string): Promise<void> {
  const field = wrapper.find(`[name="${name}"]`)
  ;(field.element as HTMLInputElement).value = text
  await field.trigger('input')
}

/** Past the typing delay, with the writes it kicked off settled. */
async function stopTyping(): Promise<void> {
  await vi.advanceTimersByTimeAsync(500)
  await flushPromises()
}

describe('RoomSettings', () => {
  it('shows the room, and follows a remote edit unless you are in the field', async () => {
    const { wrapper, room } = mountWith({ query: ['safe', 'pony'], turn_seconds: 45 })
    expect(value(wrapper, 'query')).toBe('safe, pony')
    expect(value(wrapper, 'turn_seconds')).toBe('45')

    // Someone else edits the room while we're not typing.
    room.setRoomState(roomState({ query: ['cute'], turn_seconds: 20 }))
    await nextTick()
    expect(value(wrapper, 'query')).toBe('cute')

    // Now we're mid-edit: their next broadcast must not overwrite our text.
    await wrapper.find('[name="query"]').trigger('focus')
    await type(wrapper, 'query', 'mid-edit')
    room.setRoomState(roomState({ query: ['clobber'] }))
    await nextTick()
    expect(value(wrapper, 'query')).toBe('mid-edit')
  })

  it('commits a typed field on change, sending only its own key', async () => {
    const { wrapper, configure } = mountWith()

    await wrapper.find('[name="query"]').setValue('cute, mare')

    expect(configure).toHaveBeenCalledExactlyOnceWith({ query: 'cute, mare' })
  })

  it('reaches the room once you pause, without waiting for you to leave the field', async () => {
    // Otherwise someone else's Start lands on the old query while your edit sits
    // on screen looking applied — and nothing tells you to click away first.
    vi.useFakeTimers()
    const { wrapper, configure } = mountWith({ query: ['old'] })

    await wrapper.find('[name="query"]').trigger('focus')
    await type(wrapper, 'query', 'safe, po')
    await type(wrapper, 'query', 'safe, pony')
    expect(configure).not.toHaveBeenCalled() // still typing

    await stopTyping()
    expect(configure).toHaveBeenCalledExactlyOnceWith({ query: 'safe, pony' })
    // Sent, but not re-read: normalising the text under a cursor mid-edit would
    // eat the comma you were about to type after.
    expect(value(wrapper, 'query')).toBe('safe, pony')

    vi.useRealTimers()
  })

  it('re-reads the snapshot after committing, so a rejected value snaps back', async () => {
    // 5s is below the server's floor: it drops the key and broadcasts nothing new.
    const { wrapper } = mountWith({ turn_seconds: 30 })

    await wrapper.find('[name="turn_seconds"]').setValue('5')
    await flushPromises()

    expect(value(wrapper, 'turn_seconds')).toBe('30')
  })

  it('sends a blank bound as null but keeps 0 — a real threshold, not "off"', async () => {
    // score.gte:0 excludes downvoted images, so `value || null` would be a bug.
    const { wrapper, configure } = mountWith()

    await wrapper.find('[name="min_tag_count"]').setValue('')
    await wrapper.find('[name="min_score"]').setValue('0')

    expect(configure).toHaveBeenNthCalledWith(1, { min_tag_count: null })
    expect(configure).toHaveBeenNthCalledWith(2, { min_score: 0 })
  })

  it('broadcasts a source or cap pick on the spot, and drops a cleared cap', async () => {
    const { wrapper, configure } = mountWith({ rating_caps: { rating: 'safe', darkness: 'none' } })

    await wrapper.find('[name="source"]').setValue('furbooru')
    expect(configure).toHaveBeenCalledWith({ source: 'furbooru' })

    await wrapper.find('[name="cap_rating"]').setValue('')
    expect(configure).toHaveBeenCalledWith({ rating_caps: { darkness: 'none' } })
  })

  it('renders one select per server-declared axis, from its own levels', async () => {
    // The vocabulary is the image source's, never a hardcoded list here. A lone
    // source keeps its picker hidden, so the only select is the axis's.
    const { wrapper } = mountWith({
      rating_axes: [{ key: 'mood', label: 'Mood', levels: ['calm', 'tense'] }],
      rating_caps: {},
      sources: [{ key: 'derpibooru', label: 'Derpibooru' }],
    })

    expect(wrapper.find('[name="source"]').exists()).toBe(false)
    expect(wrapper.findAll('select')).toHaveLength(1)
    const options = wrapper.find('[name="cap_mood"]').findAll('option')
    expect(options.map((o) => o.attributes('value'))).toEqual(['', 'calm', 'tense'])
    expect(wrapper.text()).toContain('Mood up to')
  })

  it('summarises the pool bounds on the folded row', () => {
    const { wrapper } = mountWith({
      min_tag_count: 15,
      min_score: null,
      rating_caps: { rating: 'suggestive' },
    })

    expect(wrapper.find('summary').text()).toContain(
      '15+ tags · any score · rating ≤ suggestive · darkness any',
    )
  })
})

describe('RoomSettings — turning on NSFW', () => {
  /** Tick the box the way a click does: the DOM flips, then `change` fires. */
  const tick = (wrapper: VueWrapper, on = true) => wrapper.find('[name="nsfw"]').setValue(on) // setValue fires change

  it('asks for 18+ first, and only broadcasts once confirmed', async () => {
    const { wrapper, configure } = mountWith()
    const session = useSessionStore()

    await tick(wrapper)
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalled()
    expect(configure).not.toHaveBeenCalled()

    await wrapper
      .findAll('button')
      .find((b) => b.text() === "I'm 18 or older")!
      .trigger('click')

    expect(session.nsfwAck).toBe(true)
    expect(configure).toHaveBeenCalledWith({ nsfw: true })
    expect(checked(wrapper, 'nsfw')).toBe(true)
  })

  it('leaves the box unticked and the room untouched when the gate is dismissed', async () => {
    const { wrapper, configure } = mountWith()

    await tick(wrapper)
    // Cancel, Escape and a backdrop click all reach the component as `close`.
    await wrapper.find('dialog').trigger('close')

    expect(checked(wrapper, 'nsfw')).toBe(false)
    expect(configure).not.toHaveBeenCalled()
  })

  it('skips the gate once attested, and never gates turning it off', async () => {
    const { wrapper, configure } = mountWith({ nsfw: true })
    useSessionStore().acknowledgeNsfw()

    await tick(wrapper, false)
    expect(configure).toHaveBeenCalledWith({ nsfw: false })

    await tick(wrapper, true)
    expect(HTMLDialogElement.prototype.showModal).not.toHaveBeenCalled()
    expect(configure).toHaveBeenCalledWith({ nsfw: true })
  })
})
