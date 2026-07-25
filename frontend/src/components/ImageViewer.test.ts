import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'

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

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

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

describe('ImageViewer controls', () => {
  it('rides in on the hint, then belongs to the pointer', async () => {
    vi.useFakeTimers()
    const wrapper = mountViewer()
    await finishLoad(wrapper)

    const controls = () => wrapper.get('[aria-label="Zoom in"]').element.parentElement!
    // Introduced alongside the gesture hint, so they're discoverable at all.
    expect(controls().className).toContain('opacity-100')

    vi.advanceTimersByTime(7100) // the hint retires
    await nextTick()
    // Gone, and non-interactive — an invisible button over the picture would
    // otherwise swallow a drag that starts on it. This is the whole point: the
    // bottom-right corner is where a signature lives.
    expect(controls().className).toContain('opacity-0')
    expect(controls().className).toContain('pointer-events-none')

    // Only hovering brings them back, and they stay for as long as it lasts.
    await wrapper.trigger('pointerenter') // the root element is the frame
    vi.advanceTimersByTime(30_000)
    await nextTick()
    expect(controls().className).toContain('opacity-100')

    await wrapper.trigger('pointerleave')
    expect(controls().className).toContain('opacity-0')
  })
})

describe('ImageViewer frame resize', () => {
  it('re-fits a fitted picture into a shorter frame, but leaves a zoom alone', async () => {
    // The on-screen keyboard opening on a phone: the frame halves in height.
    const wrapper = mountViewer()
    await finishLoad(wrapper) // 800×600 in a 400×300 frame, fit scale 0.5

    resize({ width: 400, height: 150 })
    await nextTick()
    // Keeping 0.5 here would crop the picture the moment you go to type.
    expect(wrapper.vm.view.scale).toBeCloseTo(0.25)

    resize(FRAME)
    await wrapper.get('[aria-label="Zoom in"]').trigger('click')
    expect(wrapper.vm.view.scale).toBeCloseTo(0.8)

    resize({ width: 400, height: 150 })
    await nextTick()
    // A zoom you asked for survives the keyboard; only a fit is re-fitted.
    expect(wrapper.vm.view.scale).toBeCloseTo(0.8)
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
