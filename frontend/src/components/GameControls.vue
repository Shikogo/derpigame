<script setup lang="ts">
/**
 * The turn controls that ride in the room's right rail during a live round:
 * whose turn + timer, tag progress, the guess box (or a spectator note), the
 * guess feed, and the scoreboard.
 */
import { ref } from 'vue'

import GuessFeed from '@/components/GuessFeed.vue'
import GuessInput from '@/components/GuessInput.vue'
import Scoreboard from '@/components/Scoreboard.vue'
import TagProgress from '@/components/TagProgress.vue'
import TurnIndicator from '@/components/TurnIndicator.vue'
import TurnTimer from '@/components/TurnTimer.vue'
import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'

const game = useGameStore()
const room = useRoomStore()

// Aborting can't be undone, so it goes through a confirm step instead of firing
// on the button click.
const confirmDialog = ref<HTMLDialogElement | null>(null)

function askAbort(): void {
  confirmDialog.value?.showModal()
}

function confirmAbort(): void {
  confirmDialog.value?.close()
  room.stopGame()
}

// Native <dialog> doesn't dismiss on backdrop click; a click on the element
// itself (not its content) is the backdrop.
function onBackdrop(event: MouseEvent): void {
  if (event.target === confirmDialog.value) confirmDialog.value?.close()
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="flex items-center justify-between gap-3">
      <TurnIndicator />
      <TurnTimer />
    </div>
    <TagProgress />
    <GuessInput v-if="!game.isSpectating" />
    <p v-else class="rounded-lg bg-turn/5 px-3 py-2 text-center text-sm text-ink-muted">
      👁 You're spectating — you'll join the next round.
    </p>
    <GuessFeed />
    <Scoreboard />
    <button
      v-if="game.canAbort"
      class="self-start text-xs text-ink-faint underline hover:text-wrong"
      @click="askAbort()"
    >
      Abort round
    </button>

    <dialog
      ref="confirmDialog"
      class="m-auto w-[min(24rem,90vw)] rounded-xl border border-border bg-surface p-0 text-ink shadow-2xl backdrop:bg-black/60"
      @click="onBackdrop"
    >
      <div class="flex flex-col gap-4 p-5">
        <h2 class="font-display text-xl font-bold">Abort this round?</h2>
        <p class="text-sm text-ink-muted">This ends the round for everyone and can't be undone.</p>
        <div class="flex justify-end gap-2">
          <button
            type="button"
            class="rounded-lg border border-border px-3 py-1.5 text-sm font-medium hover:bg-raised"
            @click="confirmDialog?.close()"
          >
            Cancel
          </button>
          <button
            type="button"
            class="rounded-lg bg-wrong px-4 py-1.5 text-sm font-semibold text-on-accent"
            @click="confirmAbort()"
          >
            Abort round
          </button>
        </div>
      </div>
    </dialog>
  </div>
</template>
