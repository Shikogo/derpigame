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

import { celebration, type CelebrationKind } from '@/lib/confetti'
import { CATEGORY_TOKENS } from '@/lib/tagColor'

// `kinds` fires once on mount — after `delay`, which lets a panel finish
// arriving before anything goes off on top of it. An empty `kinds` mounts an
// idle overlay that never fires.
const props = withDefaults(
  defineProps<{
    kinds?: readonly CelebrationKind[]
    delay?: number
  }>(),
  { kinds: () => [], delay: 0 },
)

/** Theme tokens the paper is cut from — canvas can't read CSS vars itself. */
const COLOR_TOKENS = [...CATEGORY_TOKENS, '--color-turn', '--color-correct']

const canvas = ref<HTMLCanvasElement | null>(null)
const timers: ReturnType<typeof setTimeout>[] = []
let launch: CreateTypes | null = null

function palette(): string[] {
  const style = getComputedStyle(document.documentElement)
  return COLOR_TOKENS.map((t) => style.getPropertyValue(t).trim()).filter(Boolean)
}

/** Send the celebration up, every shot in it held back by `delay`. */
function fire(kinds: readonly CelebrationKind[], delay: number): void {
  if (!launch || !kinds.length) return
  const view = { width: window.innerWidth, height: window.innerHeight }
  const colors = palette()
  for (const shot of celebration(kinds, view)) {
    timers.push(
      setTimeout(() => {
        // Reduced motion is the library's own opt-out: it drops the pieces in
        // place rather than animating them across the screen.
        void launch?.({ ...shot.options, colors, disableForReducedMotion: true })
      }, delay + shot.at),
    )
  }
}

onMounted(() => {
  const el = canvas.value
  if (!el) return
  launch = confetti.create(el, { resize: true, useWorker: true })
  fire(props.kinds, props.delay)
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
