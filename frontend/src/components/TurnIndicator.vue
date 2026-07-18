<script setup lang="ts">
/** Whose turn it is — the active player, or "Your turn!" when it's you. */
import { useGameStore } from '@/stores/game'

const game = useGameStore()
</script>

<template>
  <p class="text-sm font-medium">
    <span v-if="game.isMyTurn" class="font-display text-base font-bold text-turn">Your turn!</span>
    <span v-else-if="game.activePlayer">{{ game.activePlayer.name }}’s turn</span>
    <span v-else class="text-ink-faint">Waiting…</span>
  </p>
</template>
