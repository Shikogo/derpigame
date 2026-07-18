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
const remaining = ref(duration.value)
let timer: ReturnType<typeof setInterval> | undefined

// Ring geometry: the arc depletes as the turn runs out (offset 0 = full ring).
const R = 19
const CIRCUM = 2 * Math.PI * R
const dashOffset = computed(() =>
  duration.value ? CIRCUM * (1 - remaining.value / duration.value) : CIRCUM,
)

function restart(): void {
  remaining.value = duration.value
  clearInterval(timer)
  timer = setInterval(() => {
    remaining.value = Math.max(0, remaining.value - 1)
    if (remaining.value === 0) clearInterval(timer)
  }, 1000)
}

// Reset the clock at the start of each turn (including consecutive same-player turns).
watch(() => game.state.turnSeq, restart, { immediate: true })
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div
    class="relative h-11 w-11 shrink-0"
    :class="remaining <= 5 ? 'text-wrong' : 'text-turn'"
    :title="`${remaining}s left`"
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
        class="transition-[stroke-dashoffset] duration-1000 ease-linear"
      />
    </svg>
    <span
      class="absolute inset-0 flex items-center justify-center font-mono text-xs font-semibold tabular-nums"
    >
      {{ remaining }}
    </span>
  </div>
</template>
