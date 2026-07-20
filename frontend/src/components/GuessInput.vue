<script setup lang="ts">
/**
 * The dedicated guess box — enabled only on your turn (guesses are the active
 * player's alone; this is never the chat path).
 */
import { nextTick, ref, watch } from 'vue'

import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'

const game = useGameStore()
const room = useRoomStore()
const guess = ref('')
const input = ref<HTMLInputElement | null>(null)

// Focus the box when your turn begins so you can type without clicking in.
// `immediate` also covers the starting player, who is already the active player
// when this box first mounts (no false→true transition for a plain watch).
watch(
  () => game.isMyTurn,
  async (mine) => {
    if (!mine) return
    await nextTick()
    input.value?.focus()
  },
  { immediate: true },
)

async function submit(): Promise<void> {
  const value = guess.value.trim()
  if (!value || !game.isMyTurn || room.guessing) return
  guess.value = ''
  await room.submitGuess(value)
}
</script>

<template>
  <form class="flex gap-2" @submit.prevent="submit">
    <input
      ref="input"
      v-model="guess"
      :disabled="!game.isMyTurn"
      type="text"
      autocomplete="off"
      :placeholder="game.isMyTurn ? 'Guess a tag…' : 'Wait for your turn'"
      class="flex-1 rounded-lg border border-border bg-raised px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-turn focus:outline-none disabled:cursor-not-allowed disabled:bg-surface disabled:text-ink-faint"
    />
    <button
      type="submit"
      :disabled="!game.isMyTurn || !guess.trim() || room.guessing"
      class="flex min-w-20 items-center justify-center rounded-lg bg-turn px-4 py-2 text-sm font-semibold text-on-accent disabled:opacity-40"
    >
      <span
        v-if="room.guessing"
        class="h-4 w-4 animate-spin rounded-full border-2 border-on-accent/30 border-t-on-accent"
      />
      <template v-else>Guess</template>
    </button>
  </form>
</template>
