<script setup lang="ts">
/**
 * Between-rounds recap: a list of past rounds from the room snapshot. Each
 * card surfaces links to its booru page and original source on hover.
 */
import { computed, ref } from 'vue'

import AgeGate from '@/components/AgeGate.vue'
import { sourceLabel } from '@/lib/sourceLabel'
import { useRoomStore } from '@/stores/room'
import { useSessionStore } from '@/stores/session'
import type { RoundRecord } from '@/types/wire'

const room = useRoomStore()
const session = useSessionStore()

// Newest round first; the snapshot stores them oldest-first.
const rounds = computed(() => [...room.history].reverse())

// The booru-link label per round comes from the round's own source, not the
// room's current one — an old round keeps naming the booru it was played on.
function roundSource(round: RoundRecord): string {
  return sourceLabel(round.source, room.sources)
}

// A round reads as a "win" (green) only when *you* were among the winners.
function youWon(round: RoundRecord): boolean {
  return round.winners.some((w) => w.uuid === session.uuid)
}

// A round's thumbnail is NSFW based on the room's setting when it was played,
// not the room's current one — so an old NSFW round stays gated even after the
// room is switched to SFW. Hide it behind the same 18+ attestation as the live
// picture, until the viewer confirms.
const gate = ref<HTMLDialogElement | null>(null)

function isHidden(round: RoundRecord): boolean {
  return round.nsfw && !session.nsfwAck
}
function openGate(): void {
  gate.value?.showModal()
}
// While hidden, the booru/source links open the 18+ gate instead of
// navigating straight to the content.
function onLinkClick(event: MouseEvent, hidden: boolean): void {
  if (!hidden) return
  event.preventDefault()
  openGate()
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
          class="group flex items-center gap-3 rounded-lg border border-border bg-surface p-2 text-sm"
        >
          <button
            v-if="isHidden(r)"
            type="button"
            class="shrink-0"
            title="Click to reveal (18+)"
            @click="openGate"
          >
            <img
              :src="r.thumb_url"
              alt="round image"
              class="h-12 w-12 rounded object-cover blur-md"
            />
          </button>
          <img
            v-else
            :src="r.thumb_url"
            alt="round image"
            class="h-12 w-12 shrink-0 rounded object-cover"
          />

          <div class="min-w-0 flex-1">
            <p class="truncate">
              <span v-if="r.aborted" class="text-ink-faint">Aborted</span>
              <span
                v-else-if="r.winners.length"
                :class="youWon(r) ? 'text-correct' : 'text-ink-muted'"
              >
                Won by {{ r.winners.map((w) => w.name).join(', ') }}
              </span>
              <span v-else class="text-wrong">No winner</span>
            </p>
            <p v-if="r.artists.length" class="truncate text-xs text-ink-faint">
              by {{ r.artists.join(', ') }}
            </p>
          </div>

          <!-- Links reveal on hover; always shown on touch, which has no hover. -->
          <div
            class="flex shrink-0 items-center gap-1.5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 [@media(hover:none)]:opacity-100"
          >
            <a
              :href="r.page_url"
              target="_blank"
              rel="noopener noreferrer"
              class="rounded bg-raised px-2 py-1 text-xs font-medium text-turn hover:bg-turn/10"
              @click="onLinkClick($event, isHidden(r))"
            >
              {{ roundSource(r) }}
            </a>
            <a
              v-if="r.source_url"
              :href="r.source_url"
              target="_blank"
              rel="noopener noreferrer"
              class="rounded bg-raised px-2 py-1 text-xs font-medium text-turn hover:bg-turn/10"
              @click="onLinkClick($event, isHidden(r))"
            >
              Source
            </a>
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
