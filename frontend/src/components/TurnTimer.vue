<script setup lang="ts">
/**
 * Cosmetic per-turn countdown. Its duration comes from the server
 * (`state.turnSeconds`), so it matches the backend's real turn limit, but with
 * no per-turn deadline it may still drift — it never drives game logic.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { useGameStore } from '@/stores/game'

const game = useGameStore()
const duration = computed(() => game.state.turnSeconds)

// Fractional seconds left, sampled from real elapsed time each frame so the ring
// depletes smoothly. The label rounds up to whole seconds.
const remaining = ref(duration.value)
const label = computed(() => Math.max(0, Math.ceil(remaining.value)))

let start = 0
let frame: number | undefined

// Ring geometry: the arc depletes as the turn runs out (offset 0 = full ring).
const R = 19
const CIRCUM = 2 * Math.PI * R
const dashOffset = computed(() =>
  duration.value ? CIRCUM * (1 - remaining.value / duration.value) : CIRCUM,
)

function tick(now: number): void {
  remaining.value = Math.max(0, duration.value - (now - start) / 1000)
  if (remaining.value > 0) frame = requestAnimationFrame(tick)
}

function restart(): void {
  if (frame !== undefined) cancelAnimationFrame(frame)
  start = performance.now()
  remaining.value = duration.value
  frame = requestAnimationFrame(tick)
}

// Reset the clock at the start of each turn (including consecutive same-player turns).
watch(() => game.state.turnSeq, restart, { immediate: true })
onBeforeUnmount(() => {
  if (frame !== undefined) cancelAnimationFrame(frame)
})
</script>

<template>
  <div
    class="relative h-11 w-11 shrink-0"
    :class="label <= 5 ? 'text-wrong' : 'text-turn'"
    :title="`${label}s left`"
  >
    <svg class="h-full w-full -rotate-90" viewBox="0 0 44 44">
      <circle cx="22" cy="22" :r="R" fill="none" stroke="var(--color-border)" stroke-width="4" />
      <circle
        cx="22"
        cy="22"
        :r="R"
        fill="none"
        stroke="currentColor"
        stroke-width="4"
        stroke-linecap="round"
        :stroke-dasharray="CIRCUM"
        :stroke-dashoffset="dashOffset"
      />
    </svg>
    <span
      class="absolute inset-0 flex items-center justify-center font-mono text-xs font-semibold tabular-nums"
    >
      {{ label }}
    </span>
  </div>
</template>
