<script setup lang="ts">
/**
 * The dedicated guess box — typeable so you can line a guess up before your
 * turn, but only sendable on it: guesses are the active player's alone. Once
 * you're eliminated no turn is coming, so the box closes for the round.
 */
import { computed, nextTick, ref, watch } from 'vue'

import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'

const game = useGameStore()
const room = useRoomStore()
const guess = ref('')
const input = ref<HTMLInputElement | null>(null)

const placeholder = computed(() => {
  if (game.isEliminated) return "You're out of this round"
  return game.isMyTurn ? 'Guess a tag…' : 'Type ahead for your turn…'
})

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

// Being knocked out drops whatever was typed ahead — it can never be sent, and
// a stranded word would sit over the placeholder saying why.
watch(
  () => game.isEliminated,
  (out) => {
    if (out) guess.value = ''
  },
)

async function submit(): Promise<void> {
  const value = guess.value.trim()
  if (!value || !game.isMyTurn || game.isEliminated || room.guessing) return
  guess.value = ''
  // Tapping the button takes focus with it, so hand it back for the next guess.
  // Synchronously: past the `await` this is no longer the click's user gesture,
  // and mobile browsers only reopen the keyboard for a focus inside one.
  input.value?.focus()
  await room.submitGuess(value)
}
</script>

<template>
  <form class="flex gap-2" @submit.prevent="submit">
    <!-- Tags are lowercase and mostly not words, so every phone-keyboard
         nicety that assumes prose is off. -->
    <input
      ref="input"
      v-model="guess"
      type="text"
      autocomplete="off"
      enterkeyhint="send"
      autocapitalize="off"
      autocorrect="off"
      spellcheck="false"
      :disabled="game.isEliminated"
      :placeholder="placeholder"
      class="flex-1 rounded-lg border px-3 py-2 text-sm placeholder:text-ink-faint transition-colors focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
      :class="
        game.isMyTurn
          ? 'border-turn/70 bg-raised text-ink focus:border-turn focus:ring-2 focus:ring-turn/25'
          : 'border-border bg-surface text-ink-muted focus:border-ink-faint'
      "
    />
    <button
      type="submit"
      :disabled="!game.isMyTurn || game.isEliminated || !guess.trim() || room.guessing"
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
