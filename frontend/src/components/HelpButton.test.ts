import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import HelpButton from '@/components/HelpButton.vue'
import { usePreferencesStore } from '@/stores/preferences'

// jsdom has no real <dialog> modal behaviour; stub the methods the component
// calls.
beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
  HTMLDialogElement.prototype.showModal = vi.fn()
  HTMLDialogElement.prototype.close = vi.fn()
})

describe('HelpButton', () => {
  // The whole point of the flag: a new browser is told the rules, and one that's
  // been told isn't interrupted again.
  it('opens itself on a first visit only', () => {
    mount(HelpButton)
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalledOnce()
    expect(localStorage.getItem('derpigame:seenRules')).toBe('true')

    setActivePinia(createPinia())
    vi.mocked(HTMLDialogElement.prototype.showModal).mockClear()
    mount(HelpButton)
    expect(HTMLDialogElement.prototype.showModal).not.toHaveBeenCalled()
  })

  it('reopens on demand once the rules have been seen', async () => {
    usePreferencesStore().markRulesSeen()
    const wrapper = mount(HelpButton)
    expect(HTMLDialogElement.prototype.showModal).not.toHaveBeenCalled()

    await wrapper.find('button').trigger('click')
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalledOnce()
  })
})
