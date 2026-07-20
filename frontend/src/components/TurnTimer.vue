<script setup lang="ts">
/**
 * Cosmetic per-turn countdown. The ring's span is the server's turn limit
 * (`state.turnSeconds`) and the count starts at `state.turnRemaining`, which is
 * a full turn normally and the server's leftover on a rejoin. It still drifts
 * between ticks — it never drives game logic.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { useGameStore } from '@/stores/game'

const game = useGameStore()
const duration = computed(() => game.state.turnSeconds)

// Fractional seconds left, sampled from real elapsed time each frame so the ring
// depletes smoothly. The label rounds up to whole seconds.
const remaining = ref(game.state.turnRemaining)
const label = computed(() => Math.max(0, Math.ceil(remaining.value)))

let start = 0
let startRemaining = remaining.value
let frame: number | undefined

// Ring geometry: the arc depletes as the turn runs out (offset 0 = full ring).
const R = 19
const CIRCUM = 2 * Math.PI * R
const dashOffset = computed(() =>
  duration.value ? CIRCUM * (1 - remaining.value / duration.value) : CIRCUM,
)

function tick(now: number): void {
  remaining.value = Math.max(0, startRemaining - (now - start) / 1000)
  if (remaining.value > 0) frame = requestAnimationFrame(tick)
}

function restart(): void {
  if (frame !== undefined) cancelAnimationFrame(frame)
  start = performance.now()
  startRemaining = game.state.turnRemaining
  remaining.value = startRemaining
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
