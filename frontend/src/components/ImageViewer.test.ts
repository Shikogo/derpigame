import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'

import ImageViewer from '@/components/ImageViewer.vue'

// jsdom neither lays anything out nor loads images, so the two inputs the viewer
// measures against — frame size and natural size — have to be handed to it.
let resize: (size: { width: number; height: number }) => void

beforeEach(() => {
  vi.stubGlobal(
    'ResizeObserver',
    class {
      cb: ResizeObserverCallback

      constructor(cb: ResizeObserverCallback) {
        this.cb = cb
      }

      observe() {
        resize = (contentRect) =>
          this.cb([{ contentRect } as ResizeObserverEntry], this as unknown as ResizeObserver)
      }

      unobserve() {}
      disconnect() {}
    },
  )
})

afterEach(() => vi.unstubAllGlobals())

const FRAME = { width: 400, height: 300 }

function mountViewer(src = '/first.png') {
  const wrapper = mount(ImageViewer, { props: { src, alt: 'a picture' } })
  resize(FRAME)
  return wrapper
}

/** Stand in for the browser finishing a decode. Fit scale for these sizes is 0.5. */
async function finishLoad(wrapper: VueWrapper, width = 800, height = 600) {
  const img = wrapper.get('img')
  Object.defineProperty(img.element, 'naturalWidth', { value: width, configurable: true })
  Object.defineProperty(img.element, 'naturalHeight', { value: height, configurable: true })
  await img.trigger('load')
}

/** The wrapper that fades the picture in; it's transparent until the load lands. */
function imageOpacity(wrapper: VueWrapper) {
  return wrapper.get('img').element.parentElement!.className
}

describe('ImageViewer loading state', () => {
  it('keeps the picture hidden until it has fully loaded', async () => {
    const wrapper = mountViewer()
    expect(imageOpacity(wrapper)).toContain('opacity-0')
    await finishLoad(wrapper)
    expect(imageOpacity(wrapper)).toContain('opacity-100')
  })

  it('ignores a load event that carries no natural size', async () => {
    const wrapper = mountViewer()
    await wrapper.get('img').trigger('load')
    expect(imageOpacity(wrapper)).toContain('opacity-0')
  })

  it('reports a failed image instead of waiting forever', async () => {
    const wrapper = mountViewer()
    await wrapper.get('img').trigger('error')
    expect(wrapper.text()).toContain('Couldn’t load this image')
  })

  it('hides the picture again when a new round swaps it out', async () => {
    const wrapper = mountViewer()
    await finishLoad(wrapper)
    await wrapper.setProps({ src: '/second.png' })
    expect(imageOpacity(wrapper)).toContain('opacity-0')
  })
})

describe('ImageViewer loading indicator', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('announces a load that is actually taking a while', async () => {
    const wrapper = mountViewer()
    expect(wrapper.text()).not.toContain('Loading image')

    await vi.advanceTimersByTimeAsync(200)
    expect(wrapper.text()).toContain('Loading image')

    await finishLoad(wrapper)
    expect(wrapper.text()).not.toContain('Loading image')
  })

  it('stays silent for a picture that is already cached', async () => {
    const wrapper = mountViewer()
    await finishLoad(wrapper)
    await vi.advanceTimersByTimeAsync(200)
    expect(wrapper.text()).not.toContain('Loading image')
  })
})

describe('ImageViewer controls', () => {
  it('stays out of the way until there is a picture to manipulate', async () => {
    const wrapper = mountViewer()
    expect(wrapper.find('[aria-label="Zoom in"]').exists()).toBe(false)
    await finishLoad(wrapper)
    expect(wrapper.find('[aria-label="Zoom in"]').exists()).toBe(true)
  })

  it('zooms in a notch at a time and resets back to fit', async () => {
    const wrapper = mountViewer()
    await finishLoad(wrapper)
    expect(wrapper.vm.view.scale).toBeCloseTo(0.5) // fit

    await wrapper.get('[aria-label="Zoom in"]').trigger('click')
    expect(wrapper.vm.view.scale).toBeCloseTo(0.8) // 0.5 × 1.6

    await wrapper.get('[aria-label="Reset to fit"]').trigger('click')
    expect(wrapper.vm.view.scale).toBeCloseTo(0.5)
  })

  it('offers zoom-out and reset only once they would do something', async () => {
    const wrapper = mountViewer()
    await finishLoad(wrapper)
    expect(wrapper.get('[aria-label="Zoom out"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[aria-label="Reset to fit"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[aria-label="Zoom in"]').trigger('click')
    expect(wrapper.get('[aria-label="Zoom out"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('[aria-label="Reset to fit"]').attributes('disabled')).toBeUndefined()
  })

  it('shows the zoom level only while zoomed in', async () => {
    const wrapper = mountViewer()
    await finishLoad(wrapper)
    expect(wrapper.text()).not.toContain('100%')

    await wrapper.get('[aria-label="Zoom in"]').trigger('click')
    expect(wrapper.text()).toContain('160%')
  })
})

describe('ImageViewer gesture hint', () => {
  it('spells the gestures out when the first picture arrives', async () => {
    const wrapper = mountViewer()
    expect(wrapper.text()).not.toContain('Drag to pan')
    await finishLoad(wrapper)
    expect(wrapper.text()).toContain('Drag to pan')
  })

  it('drops the hint once the player starts interacting', async () => {
    const wrapper = mountViewer()
    await finishLoad(wrapper)
    await wrapper.get('[aria-label="Zoom in"]').trigger('click')
    expect(wrapper.text()).not.toContain('Drag to pan')
  })

  it('does not repeat itself on later rounds', async () => {
    const wrapper = mountViewer()
    await finishLoad(wrapper)
    await wrapper.get('[aria-label="Zoom in"]').trigger('click')

    await wrapper.setProps({ src: '/second.png' })
    await finishLoad(wrapper)
    expect(wrapper.text()).not.toContain('Drag to pan')
  })
})
