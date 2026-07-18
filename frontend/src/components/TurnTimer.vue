<script setup lang="ts">
/**
 * Cosmetic per-turn countdown. `turn_started` carries no server deadline yet, so
 * this is a local clock that resets each turn and may drift — it never drives
 * game logic (the backend owns timeouts).
 */
import { onBeforeUnmount, ref, watch } from 'vue'

import { useGameStore } from '@/stores/game'

const TURN_SECONDS = 30

const game = useGameStore()
const remaining = ref(TURN_SECONDS)
let timer: ReturnType<typeof setInterval> | undefined

function restart(): void {
  remaining.value = TURN_SECONDS
  clearInterval(timer)
  timer = setInterval(() => {
    remaining.value = Math.max(0, remaining.value - 1)
    if (remaining.value === 0) clearInterval(timer)
  }, 1000)
}

// Reset the clock at the start of each turn.
watch(() => game.activePlayer?.uuid, (uuid) => uuid && restart(), { immediate: true })
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div class="flex items-center gap-2 text-xs" :class="remaining <= 5 ? 'text-wrong' : 'text-gray-400'">
    <span class="w-6 text-right font-semibold tabular-nums">{{ remaining }}s</span>
    <div class="h-1.5 w-16 overflow-hidden rounded-full bg-gray-200">
      <div
        class="h-full rounded-full bg-turn transition-[width] duration-1000 ease-linear"
        :style="{ width: `${(remaining / TURN_SECONDS) * 100}%` }"
      />
    </div>
  </div>
</template>
