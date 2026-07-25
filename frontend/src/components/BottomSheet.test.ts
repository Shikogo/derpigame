import { afterEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import BottomSheet from '@/components/BottomSheet.vue'

function mountSheet(props: { open: boolean }) {
  return mount(BottomSheet, {
    props,
    slots: { default: '<p>contents</p>' },
    attachTo: document.body,
  })
}

/** The sheet's own element, ignoring the teleported backdrop. */
function panel(wrapper: ReturnType<typeof mountSheet>) {
  return wrapper.get('#round-sheet')
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('BottomSheet', () => {
  it('hides while closed, and shows itself with a backdrop when opened', async () => {
    const wrapper = mountSheet({ open: false })

    expect(panel(wrapper).classes()).toContain('max-lg:invisible')
    expect(panel(wrapper).classes()).toContain('max-lg:translate-y-full')
    expect(document.querySelector('.fixed.inset-0')).toBe(null)

    await wrapper.setProps({ open: true })

    expect(panel(wrapper).classes()).not.toContain('max-lg:invisible')
    expect(panel(wrapper).classes()).toContain('max-lg:translate-y-0')
    expect(document.querySelector('.fixed.inset-0')).not.toBe(null)

    wrapper.unmount()
  })

  it('closes on a backdrop click and on Escape', async () => {
    const wrapper = mountSheet({ open: true })

    const backdrop = document.querySelector('.fixed.inset-0') as HTMLElement
    backdrop.click()
    expect(wrapper.emitted('update:open')?.at(-1)).toEqual([false])

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('update:open')).toHaveLength(2)

    wrapper.unmount()
  })

  it('leaves Escape alone while closed', async () => {
    // Nothing is open to escape from, and Escape belongs to whatever dialog is up.
    const wrapper = mountSheet({ open: false })
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('update:open')).toBeUndefined()
    wrapper.unmount()
  })
})
