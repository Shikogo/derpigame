import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import HomeView from '@/views/HomeView.vue'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/room/:code', name: 'room', component: { template: '<div />' } },
  ],
})

function mountHome() {
  return mount(HomeView, { global: { plugins: [createPinia(), router] } })
}

describe('HomeView', () => {
  it('renders the title and both entry paths', () => {
    const wrapper = mountHome()
    expect(wrapper.text()).toContain('derpigame')
    expect(wrapper.text()).toContain('Create a room')
    expect(wrapper.find('input').exists()).toBe(true)
  })

  it('disables create until a name is entered', async () => {
    const wrapper = mountHome()
    const createBtn = wrapper.findAll('button').find((b) => b.text() === 'Create a room')!
    expect(createBtn.attributes('disabled')).toBeDefined()

    await wrapper.find('input').setValue('Twilight')
    expect(createBtn.attributes('disabled')).toBeUndefined()
  })
})
