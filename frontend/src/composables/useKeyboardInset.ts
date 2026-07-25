/**
 * The on-screen keyboard's height, as a reactive number and as a `--kbd-inset`
 * custom property on the document element.
 *
 * The room's mobile shell is a fixed-height box with the guess bar along its
 * bottom edge, and `100dvh` tracks the browser's chrome, not the keyboard — so
 * on Safari the bar would sit under the keys. Measuring the visual viewport is
 * the only way to know. Chrome needs none of this (`interactive-widget` in the
 * viewport meta already shrank the layout viewport); there the measurement lands
 * at 0 and `dvh` does the work, so the two never double-count.
 *
 * The CSS variable is the primary consumer — the shell's height and the sheet's
 * offset both need it, and one `:root` property beats threading pixels through
 * the components between them.
 */

import {
  computed,
  onBeforeUnmount,
  onMounted,
  readonly,
  ref,
  type ComputedRef,
  type Ref,
} from 'vue'

import { keyboardInset } from '@/lib/viewportInsets'

const inset = ref(0)
let consumers = 0

function measure(): void {
  const viewport = window.visualViewport
  if (!viewport) return
  const next = keyboardInset({
    innerHeight: window.innerHeight,
    viewportHeight: viewport.height,
    offsetTop: viewport.offsetTop,
    scale: viewport.scale,
  })
  if (next === inset.value) return
  inset.value = next
  document.documentElement.style.setProperty('--kbd-inset', `${next}px`)
}

export function useKeyboardInset(): {
  inset: Readonly<Ref<number>>
  open: ComputedRef<boolean>
} {
  onMounted(() => {
    // No visual viewport (jsdom, ancient browsers): stay at 0 and publish
    // nothing, so `var(--kbd-inset, 0px)` falls back and the layout is simply
    // the one without a keyboard.
    if (!window.visualViewport) return
    if (consumers++ === 0) {
      window.visualViewport.addEventListener('resize', measure)
      window.visualViewport.addEventListener('scroll', measure)
      window.addEventListener('resize', measure)
    }
    measure()
  })

  onBeforeUnmount(() => {
    if (!window.visualViewport) return
    if (--consumers > 0) return
    window.visualViewport.removeEventListener('resize', measure)
    window.visualViewport.removeEventListener('scroll', measure)
    window.removeEventListener('resize', measure)
    inset.value = 0
    document.documentElement.style.removeProperty('--kbd-inset')
  })

  return { inset: readonly(inset), open: computed(() => inset.value > 0) }
}
