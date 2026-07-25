<script setup lang="ts">
/**
 * The round's record: every guess so far, the standings, and the way out. Not
 * needed to play — the overlay cards carry the verdict as it lands — so on a
 * phone this rides in the sheet behind the guess box rather than on screen.
 */
import { ref } from 'vue'

import GuessFeed from '@/components/GuessFeed.vue'
import Scoreboard from '@/components/Scoreboard.vue'
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
