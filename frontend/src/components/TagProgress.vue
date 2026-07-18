<script setup lang="ts">
/** Goal-bucket progress bar plus a chip per remaining bonus bucket. */
import { computed } from 'vue'

import { useGameStore } from '@/stores/game'

const game = useGameStore()

const found = computed(() => game.state.goalTagCount - game.state.goalRemaining)
const pct = computed(() =>
  game.state.goalTagCount ? (found.value / game.state.goalTagCount) * 100 : 0,
)
// Bucket keys are opaque (source-defined taxonomy) — render them as-is.
const bonuses = computed(() => Object.entries(game.state.bonusCounts))
</script>

<template>
  <div class="space-y-2">
    <div class="flex items-center justify-between text-sm">
      <span class="font-medium">Tags found</span>
      <span class="tabular-nums text-gray-500">{{ found }} / {{ game.state.goalTagCount }}</span>
    </div>
    <div class="h-2 overflow-hidden rounded-full bg-gray-200">
      <div class="h-full rounded-full bg-correct transition-[width]" :style="{ width: `${pct}%` }" />
    </div>
    <div v-if="bonuses.length" class="flex flex-wrap gap-1.5">
      <span
        v-for="[bucket, n] in bonuses"
        :key="bucket"
        class="rounded-full bg-turn/10 px-2 py-0.5 text-xs font-medium text-turn"
      >
        {{ bucket }}: {{ n }} left
      </span>
    </div>
  </div>
</template>
