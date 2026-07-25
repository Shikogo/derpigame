<script setup lang="ts">
/**
 * Full-screen confetti, fired once on mount and left to fall. `canvas-confetti`
 * does the animating; this owns the canvas, the schedule and the theme palette.
 *
 * The canvas is teleported to `<body>`, and has to be: a transformed ancestor
 * becomes the containing block for `position: fixed`, so mounted in place it
 * would be sized to whichever panel holds it for as long as the panel
 * transition's `translateY` is applied.
 *
 * `useWorker` hands the animation to an OffscreenCanvas in a worker, which is
 * what keeps a heavy volley off the main thread.
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import confetti, { type CreateTypes } from 'canvas-confetti'

import {
  DEFAULT_TUNING,
  celebration,
  type CelebrationKind,
  type ConfettiTuning,
} from '@/lib/confetti'

// `kinds` fires once on mount — after `delay`, which lets a panel finish
// arriving before anything goes off on top of it. Leaving it empty mounts an
// idle overlay for a caller that would rather drive `fire()` itself: the
// sandbox, which stacks shots. `tuning` is that caller's hook for dialling the
// feel in live; the game never passes it.
const props = withDefaults(
  defineProps<{
    kinds?: readonly CelebrationKind[]
    delay?: number
    tuning?: ConfettiTuning
  }>(),
  { kinds: () => [], delay: 0, tuning: () => DEFAULT_TUNING },
)

/** Theme tokens the paper is cut from — canvas can't read CSS vars itself. */
const COLOR_TOKENS = [
  '--color-cat-1',
  '--color-cat-2',
  '--color-cat-3',
  '--color-cat-4',
  '--color-cat-5',
  '--color-turn',
  '--color-correct',
]

const canvas = ref<HTMLCanvasElement | null>(null)
const timers: ReturnType<typeof setTimeout>[] = []
let launch: CreateTypes | null = null

function palette(): string[] {
  const style = getComputedStyle(document.documentElement)
  return COLOR_TOKENS.map((t) => style.getPropertyValue(t).trim()).filter(Boolean)
}

/**
 * Send up another celebration. Shots stack rather than replace: the library
 * keeps animating whatever is already in the air.
 */
function fire(kinds: readonly CelebrationKind[]): void {
  if (!launch || !kinds.length) return
  const view = { width: window.innerWidth, height: window.innerHeight }
  const colors = palette()
  for (const shot of celebration(kinds, view, props.tuning)) {
    timers.push(
      setTimeout(() => {
        // Reduced motion is the library's own opt-out: it drops the pieces in
        // place rather than animating them across the screen.
        void launch?.({ ...shot.options, colors, disableForReducedMotion: true })
      }, shot.at),
    )
  }
}

defineExpose({ fire })

onMounted(() => {
  const el = canvas.value
  if (!el) return
  launch = confetti.create(el, { resize: true, useWorker: true })
  if (props.kinds.length) timers.push(setTimeout(() => fire(props.kinds), props.delay))
})

onBeforeUnmount(() => {
  for (const t of timers) clearTimeout(t)
  launch?.reset()
})
</script>

<template>
  <!-- Out to <body>, clear of any transformed ancestor — see the note above.
       `h-full w-full` is load-bearing: a canvas is a replaced element, so
       `inset-0` alone leaves it at its intrinsic size. -->
  <Teleport to="body">
    <canvas
      ref="canvas"
      class="pointer-events-none fixed inset-0 z-40 h-full w-full"
      aria-hidden="true"
    />
  </Teleport>
</template>
