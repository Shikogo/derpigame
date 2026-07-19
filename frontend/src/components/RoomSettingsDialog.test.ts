import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import RoomSettingsDialog from '@/components/RoomSettingsDialog.vue'
import { useRoomStore } from '@/stores/room'
import { roomState } from '@/test/factories'
import type { RoomState } from '@/types/wire'

// jsdom has no real <dialog> modal behaviour; stub the methods the component calls.
beforeEach(() => {
  setActivePinia(createPinia())
  HTMLDialogElement.prototype.showModal = vi.fn()
  HTMLDialogElement.prototype.close = vi.fn()
})

/** Seed the store, mount, and open the dialog — the state every test starts from. */
async function openWith(over: Partial<RoomState> = {}) {
  const room = useRoomStore()
  room.setRoomState(roomState(over))
  const configure = vi.spyOn(room, 'configureRoom').mockResolvedValue({ ok: true })

  const wrapper = mount(RoomSettingsDialog)
  ;(wrapper.vm as unknown as { open: () => void }).open()
  await nextTick()

  return { wrapper, configure }
}

const value = (wrapper: VueWrapper, name: string) =>
  (wrapper.find(`[name="${name}"]`).element as HTMLInputElement | HTMLSelectElement).value

describe('RoomSettingsDialog', () => {
  it('seeds every control from the current snapshot each time it opens', async () => {
    const { wrapper } = await openWith({
      query: ['safe', 'pony'],
      nsfw: true,
      turn_seconds: 45,
      min_tag_count: 20,
      min_score: 50,
      rating_caps: { rating: 'questionable' },
    })

    expect(value(wrapper, 'query')).toBe('safe, pony')
    expect((wrapper.find('[name="nsfw"]').element as HTMLInputElement).checked).toBe(true)
    expect(value(wrapper, 'turn_seconds')).toBe('45')
    expect(value(wrapper, 'min_tag_count')).toBe('20')
    expect(value(wrapper, 'min_score')).toBe('50')
    expect(value(wrapper, 'cap_rating')).toBe('questionable')
    expect(value(wrapper, 'cap_darkness')).toBe('') // uncapped axis
  })

  it('seeds a disabled bound as blank rather than as a number', async () => {
    const { wrapper } = await openWith({ min_tag_count: null, min_score: null })

    expect(value(wrapper, 'min_tag_count')).toBe('')
    expect(value(wrapper, 'min_score')).toBe('')
  })

  it('applying broadcasts every edited setting via configureRoom', async () => {
    const { wrapper, configure } = await openWith()

    await wrapper.find('[name="query"]').setValue('cute, mare')
    await wrapper.find('[name="nsfw"]').setValue(true)
    await wrapper.find('[name="turn_seconds"]').setValue('60')
    await wrapper.find('[name="min_tag_count"]').setValue('20')
    await wrapper.find('[name="min_score"]').setValue('50')
    await wrapper.find('[name="cap_rating"]').setValue('suggestive')
    await wrapper.find('form').trigger('submit')

    expect(configure).toHaveBeenCalledWith({
      query: 'cute, mare',
      nsfw: true,
      turn_seconds: 60,
      min_tag_count: 20,
      min_score: 50,
      rating_caps: { rating: 'suggestive' },
    })
  })

  it('sends a blank bound as null (the setting off)', async () => {
    const { wrapper, configure } = await openWith()

    await wrapper.find('[name="min_tag_count"]').setValue('')
    await wrapper.find('[name="min_score"]').setValue('')
    await wrapper.find('form').trigger('submit')

    expect(configure).toHaveBeenCalledWith(
      expect.objectContaining({ min_tag_count: null, min_score: null }),
    )
  })

  it('keeps a zero bound as 0 — a real threshold, not "off"', async () => {
    // score.gte:0 excludes downvoted images, so `value || null` would be a bug.
    const { wrapper, configure } = await openWith()

    await wrapper.find('[name="min_tag_count"]').setValue('0')
    await wrapper.find('[name="min_score"]').setValue('0')
    await wrapper.find('form').trigger('submit')

    expect(configure).toHaveBeenCalledWith(
      expect.objectContaining({ min_tag_count: 0, min_score: 0 }),
    )
  })

  it('drops a cleared cap instead of sending it as a level', async () => {
    const { wrapper, configure } = await openWith({
      rating_caps: { rating: 'safe', darkness: 'none' },
    })

    await wrapper.find('[name="cap_rating"]').setValue('')
    await wrapper.find('form').trigger('submit')

    expect(configure).toHaveBeenCalledWith(
      expect.objectContaining({ rating_caps: { darkness: 'none' } }),
    )
  })

  it('renders one select per server-declared axis, from its own levels', async () => {
    // The vocabulary is the image source's, never a hardcoded list here.
    const { wrapper } = await openWith({
      rating_axes: [{ key: 'mood', label: 'Mood', levels: ['calm', 'tense'] }],
      rating_caps: {},
    })

    expect(wrapper.findAll('select')).toHaveLength(1)
    const options = wrapper.find('[name="cap_mood"]').findAll('option')
    expect(options.map((o) => o.attributes('value'))).toEqual(['', 'calm', 'tense'])
    expect(wrapper.text()).toContain('Mood up to')
  })

  it('does not broadcast when cancelled', async () => {
    const { wrapper, configure } = await openWith()

    await wrapper.find('[name="query"]').setValue('discarded')
    await wrapper.findAll('button').find((b) => b.text() === 'Cancel')!.trigger('click')

    expect(configure).not.toHaveBeenCalled()
  })
})
