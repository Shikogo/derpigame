<script setup lang="ts">
/**
 * The dedicated guess box — enabled only on your turn (guesses are the active
 * player's alone; this is never the chat path).
 */
import { ref } from 'vue'

import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'

const game = useGameStore()
const room = useRoomStore()
const guess = ref('')

async function submit(): Promise<void> {
  const value = guess.value.trim()
  if (!value || !game.isMyTurn) return
  guess.value = ''
  await room.submitGuess(value)
}
</script>

<template>
  <form class="flex gap-2" @submit.prevent="submit">
    <input
      v-model="guess"
      :disabled="!game.isMyTurn"
      type="text"
      autocomplete="off"
      :placeholder="game.isMyTurn ? 'Guess a tag…' : 'Wait for your turn'"
      class="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-turn focus:outline-none disabled:cursor-not-allowed disabled:bg-gray-100"
    />
    <button
      type="submit"
      :disabled="!game.isMyTurn || !guess.trim()"
      class="rounded-lg bg-turn px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
    >
      Guess
    </button>
  </form>
</template>
