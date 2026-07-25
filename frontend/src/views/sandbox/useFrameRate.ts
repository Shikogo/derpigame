/**
 * Frame-rate sampling for the dev harnesses, measured independently of whatever
 * is being judged. "Feels laggy" is hard to act on; a worst-frame figure isn't.
 */

import { onBeforeUnmount, ref } from 'vue'

/**
 * How often the rate is published. A figure recomputed every frame is both
 * unreadable and misleading — it reports the last gap, not the rate.
 */
const WINDOW_MS = 250

/**
 * How long one `watch()` keeps sampling for. Sampling forever would leave a
 * rAF callback running for the life of the page and let the readout drift back
 * to an idle 60 — the interesting number is the one from while the paper flew.
 */
const RUN_MS = 8000

export function useFrameRate() {
  const fps = ref(0)
  const worst = ref(0)
  const janky = ref(0) // frames over 20ms — the ones that read as a stutter
  let handle = 0
  let previous = 0
  let windowStart = 0
  let windowFrames = 0
  let until = 0

  function sample(now: number): void {
    if (previous) {
      const delta = now - previous
      worst.value = Math.max(worst.value, Math.round(delta))
      if (delta > 20) janky.value++
    }
    previous = now
    windowFrames++
    if (!windowStart) windowStart = now
    else if (now - windowStart >= WINDOW_MS) {
      fps.value = Math.round((windowFrames * 1000) / (now - windowStart))
      windowStart = now
      windowFrames = 0
    }
    if (now >= until) {
      handle = 0 // done; the last published figures stand as the run's record
      return
    }
    handle = requestAnimationFrame(sample)
  }

  /** Sample the next few seconds. Firing again extends an in-flight run. */
  function watch(): void {
    until = performance.now() + RUN_MS
    if (handle) return
    previous = 0
    windowStart = 0
    windowFrames = 0
    handle = requestAnimationFrame(sample)
  }

  function reset(): void {
    worst.value = 0
    janky.value = 0
  }

  onBeforeUnmount(() => cancelAnimationFrame(handle))

  return { fps, worst, janky, watch, reset }
}
