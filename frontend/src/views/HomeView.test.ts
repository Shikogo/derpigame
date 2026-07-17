import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import HomeView from '@/views/HomeView.vue'

describe('HomeView', () => {
  it('renders the title', () => {
    const wrapper = mount(HomeView)
    expect(wrapper.text()).toContain('Derpigame')
  })
})
