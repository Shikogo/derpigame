<script setup lang="ts">
/**
 * Between-rounds recap: the win leaderboard and a list of past rounds (each
 * links to its derpibooru page). Both come straight from the room snapshot.
 */
import { computed, ref } from 'vue'

import AgeGate from '@/components/AgeGate.vue'
import { useRoomStore } from '@/stores/room'
import { useSessionStore } from '@/stores/session'
import type { RoundRecord } from '@/types/wire'

const room = useRoomStore()
const session = useSessionStore()

// Newest round first; the snapshot stores them oldest-first.
const rounds = computed(() => [...room.history].reverse())

// A round reads as a "win" (green) only when *you* were among the winners.
function youWon(round: RoundRecord): boolean {
  return round.winners.some((w) => w.uuid === session.uuid)
}

// Past-round thumbnails are NSFW when the room is; hide them behind the same
// 18+ attestation as the live picture. Clicking a hidden thumb opens the gate
// (it never reveals without the confirmation).
const hideThumbs = computed(() => room.nsfw && !session.nsfwAck)
const gate = ref<HTMLDialogElement | null>(null)

function onThumbClick(event: MouseEvent): void {
  if (!hideThumbs.value) return // revealed: let the link open the derpibooru page
  event.preventDefault()
  gate.value?.showModal()
}
function attest(): void {
  session.acknowledgeNsfw()
  gate.value?.close()
}
function onBackdrop(event: MouseEvent): void {
  if (event.target === gate.value) gate.value?.close()
}
</script>

<template>
  <section v-if="rounds.length" class="flex flex-col gap-3">
    <div>
      <h3 class="mb-1.5 text-sm font-semibold text-ink-muted">Past rounds</h3>
      <ul class="flex flex-col gap-2">
        <li
          v-for="(r, i) in rounds"
          :key="i"
          class="flex items-center gap-3 rounded-lg border border-border bg-surface p-2 text-sm"
        >
          <a
            :href="r.page_url"
            target="_blank"
            rel="noopener noreferrer"
            class="shrink-0"
            :title="hideThumbs ? 'Click to reveal (18+)' : undefined"
            @click="onThumbClick"
          >
            <img
              :src="r.thumb_url"
              alt="round image"
              class="h-12 w-12 rounded object-cover"
              :class="{ 'blur-md': hideThumbs }"
            />
          </a>
          <div class="min-w-0 flex-1">
            <p class="truncate">
              <span v-if="r.aborted" class="text-ink-faint">Stopped</span>
              <span v-else-if="r.winners.length" :class="youWon(r) ? 'text-correct' : 'text-ink-muted'">
                Won by {{ r.winners.map((w) => w.name).join(', ') }}
              </span>
              <span v-else class="text-wrong">No winner</span>
            </p>
            <p v-if="r.artists.length" class="truncate text-xs text-ink-faint">
              by {{ r.artists.join(', ') }}
            </p>
          </div>
        </li>
      </ul>
    </div>

    <dialog
      ref="gate"
      class="m-auto w-[min(28rem,90vw)] bg-transparent p-0 backdrop:bg-black/60"
      @click="onBackdrop"
    >
      <AgeGate decline-label="Not now" @confirm="attest" @decline="gate?.close()" />
    </dialog>
  </section>
</template>
