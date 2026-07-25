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

export function useFrameRate() {
  const fps = ref(0)
  const worst = ref(0)
  const janky = ref(0) // frames over 20ms — the ones that read as a stutter
  let handle = 0
  let previous = 0
  let windowStart = 0
  let windowFrames = 0

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
    handle = requestAnimationFrame(sample)
  }

  /** Start sampling, or keep going if it already is. */
  function watch(): void {
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
