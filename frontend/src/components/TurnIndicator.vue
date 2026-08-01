<script setup lang="ts">
/** Whose turn it is — the active player, or "Your turn!" when it's you. */
import { useGameStore } from '@/stores/game'

// Wears the accent for a moment as the turn lands.
withDefaults(defineProps<{ banner?: boolean }>(), { banner: false })

const game = useGameStore()
</script>

<template>
  <p class="text-sm font-medium">
    <span
      v-if="game.isMyTurn"
      class="font-display text-base font-bold"
      :class="banner && 'banner pill bg-turn tracking-wide text-on-accent'"
    >
      <span v-if="banner" aria-hidden="true">▶</span>
      <!-- The text stays exactly "Your turn!" — the e2e suite matches it. -->
      <span :class="banner ? 'uppercase' : 'text-turn'">Your turn!</span>
    </span>
    <span v-else-if="game.activePlayer">{{ game.activePlayer.name }}’s turn</span>
    <span v-else class="text-ink-faint">Waiting…</span>
  </p>
</template>

<style scoped>
.banner {
  animation: banner-sweep 0.32s cubic-bezier(0.2, 1.4, 0.4, 1) backwards;
}

@keyframes banner-sweep {
  from {
    opacity: 0;
    transform: translateX(-0.5rem);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
</style>
