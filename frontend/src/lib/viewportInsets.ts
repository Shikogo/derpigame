/**
 * How much of the layout viewport the on-screen keyboard covers — pure, so the
 * awkward part (telling a keyboard apart from browser chrome, a pinch-zoom, and
 * a layout viewport the browser already shrank for us) is testable without a
 * phone. `useKeyboardInset` owns the listeners.
 */

export interface VisualViewportSample {
  /** Layout viewport height, i.e. `window.innerHeight`. */
  innerHeight: number
  /** Visual viewport height, i.e. `visualViewport.height`. */
  viewportHeight: number
  /** How far the visual viewport has scrolled down the layout viewport. */
  offsetTop: number
  scale?: number
}

/** Below this, the gap is browser chrome or rounding, not a keyboard. */
export const KEYBOARD_MIN_PX = 120

// A pinch of a percent or two is measurement noise, not a deliberate zoom.
const SCALE_SLACK = 1.05

export function keyboardInset(sample: VisualViewportSample): number {
  // A pinched page shrinks the visual viewport too, and that isn't a keyboard.
  if ((sample.scale ?? 1) > SCALE_SLACK) return 0
  // offsetTop comes off the top because iOS Safari scrolls the layout viewport
  // up when an input is focused, which otherwise reads as extra keyboard.
  const covered = sample.innerHeight - sample.viewportHeight - sample.offsetTop
  // Where the browser already shrank the layout viewport for us (Chrome with
  // `interactive-widget=resizes-content`), both heights moved together and this
  // lands at ~0 — which is what keeps `dvh` and this measurement from
  // double-counting the same keyboard.
  return covered < KEYBOARD_MIN_PX ? 0 : Math.round(covered)
}
