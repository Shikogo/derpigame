<script setup lang="ts">
/**
 * The guess box and, on a phone, the handle for the sheet holding everything
 * that isn't the guess box. Docked along the bottom of the mobile shell, where
 * it rides above the keyboard; in the rail it's just the box.
 *
 * `data-guess-dock` marks it for `GuessOverlay`, which dismisses its card on any
 * pointer press and has to make an exception for this one.
 */
import GuessInput from '@/components/GuessInput.vue'
import { useGameStore } from '@/stores/game'

defineProps<{ unread: number; sheetOpen: boolean }>()
const emit = defineEmits<{ toggle: [] }>()

const game = useGameStore()
</script>

<template>
  <div
    data-guess-dock
    class="flex flex-col gap-2 max-lg:border-t max-lg:border-border max-lg:bg-surface max-lg:px-3 max-lg:py-2"
  >
    <GuessInput v-if="!game.isSpectating" />
    <p v-else class="rounded-lg bg-turn/5 px-3 py-2 text-center text-sm text-ink-muted">
      👁 You're spectating — you'll join the next round.
    </p>

    <!-- Mobile only: the rail shows the sheet's contents inline, so there's
         nothing to pull up. Hidden rather than absent so the dock renders the
         same in both, minus a display:none child. -->
    <button
      type="button"
      class="relative flex items-center justify-center gap-2 py-1 lg:hidden"
      :aria-expanded="sheetOpen"
      aria-controls="round-sheet"
      :aria-label="sheetOpen ? 'Hide guesses, scores and chat' : 'Show guesses, scores and chat'"
      @click="emit('toggle')"
    >
      <span class="h-1 w-10 rounded-full bg-border" />
      <span aria-hidden="true" class="text-xs leading-none text-ink-faint">
        {{ sheetOpen ? '▼' : '▲' }}
      </span>
      <span v-if="unread" class="absolute right-2 top-1.5 h-2 w-2 rounded-full bg-turn">
        <span class="sr-only">{{ unread }} unread chat messages</span>
      </span>
    </button>
  </div>
</template>
