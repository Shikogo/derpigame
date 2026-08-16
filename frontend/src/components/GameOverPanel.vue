<script setup lang="ts">
/**
 * End-of-round screen for both a finished game and an aborted one. Either way it
 * reveals the image — still pan/zoomable, so the tags you missed are worth a
 * second look — plus its attribution and the tag recap; a finished game also
 * shows winners, standings and the confetti. The ready/start bar stays on screen
 * throughout, so the next round is one click away without a trip to the lobby.
 */
import { computed, ref, watch } from 'vue'

import ConfettiOverlay from '@/components/ConfettiOverlay.vue'
import ImageViewer from '@/components/ImageViewer.vue'
import ReadyBar from '@/components/ReadyBar.vue'
import RoundSummary from '@/components/RoundSummary.vue'
import type { CelebrationKind } from '@/lib/confetti'
import { sourceLabel } from '@/lib/sourceLabel'
import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'
import { useSessionStore } from '@/stores/session'

// `arrivals` ticks when a panel finishes arriving (see `RoomView`). The cannons
// wait for a tick that lands while this panel is mounted — a shot fired mid-fade
// fights the transition.
const props = defineProps<{ arrivals?: number }>()
const emit = defineEmits<{ back: [] }>()

const arrived = ref(false)
watch(
  () => props.arrivals,
  () => (arrived.value = true),
)

const game = useGameStore()
const room = useRoomStore()
const session = useSessionStore()

// The round's own source, not the room's — switching booru mid-recap must not
// relabel the link under a picture that came from the other one.
const booru = computed(() =>
  game.state.source ? sourceLabel(game.state.source, room.sources) : 'the booru',
)

const aborted = computed(() => game.state.status === 'aborted')
const over = computed(() => game.state.over)
const reveal = computed(() => game.state.reveal)
const image = computed(() => game.state.image)
const iWon = computed(() => over.value?.winners.some((w) => w.uuid === session.uuid) ?? false)

// The tally the round itself reported, so it already counts this one.
const winsByUuid = computed(() => new Map(over.value?.winCounts.map((w) => [w.uuid, w.wins])))
const wins = (uuid: string): number => winsByUuid.value.get(uuid) ?? 0

// Winning is scoring the most points, not clearing every tag — that's a rare
// bonus, celebrated separately below rather than framing the whole result.
const winnerList = new Intl.ListFormat('en', { type: 'conjunction' })

const heading = computed(() => {
  if (aborted.value) return 'Round aborted'
  const winners = over.value?.winners ?? []
  if (!winners.length) return 'Round over'
  // A tie names everyone who shares it, you included — you just lead the list,
  // as "You", rather than replacing it.
  const names = [
    ...(iWon.value ? ['You'] : []),
    ...winners.filter((w) => w.uuid !== session.uuid).map((w) => w.name),
  ]
  return `${winnerList.format(names)} won!${iWon.value ? ' 🎉' : ''}`
})

// Two separate things to celebrate, and you can have either or both: the cannons
// are personal — you get them for winning — while a clean sweep is the room's
// doing, so its fireworks play for everyone, winner or not. `aborted` leads, as
// in the heading: a stopped round is never celebrated.
const celebration = computed<CelebrationKind[]>(() => {
  if (aborted.value || !over.value) return []
  const kinds: CelebrationKind[] = []
  if (iWon.value) kinds.push('winner')
  if (over.value.win) kinds.push('sweep')
  return kinds
})
</script>

<template>
  <section class="mx-auto flex w-full max-w-3xl flex-col gap-5 lg:p-4">
    <ConfettiOverlay v-if="celebration.length && arrived" :kinds="celebration" />

    <h2 class="font-display text-3xl font-bold" :class="iWon ? 'text-correct' : 'text-turn'">
      {{ heading }}
    </h2>

    <p
      v-if="over?.win"
      class="sweep -mt-3 self-start rounded-lg bg-correct/10 px-3 py-1.5 text-sm font-semibold text-correct ring-1 ring-correct/30"
    >
      🏆 Clean sweep — every goal tag guessed!
    </p>

    <!-- Fixed height: the viewer frame needs a definite one to measure against,
         and the standings below it still have to fit on screen. -->
    <div v-if="image" class="h-[50vh] overflow-hidden rounded-lg border border-border">
      <ImageViewer :src="image.full_url" alt="The revealed image" />
    </div>

    <div v-if="reveal" class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
      <span v-if="reveal.artists.length" class="font-medium"
        >by {{ reveal.artists.join(', ') }}</span
      >
      <span v-else class="text-ink-faint">artist unknown</span>
      <a
        v-if="reveal.source_url"
        :href="reveal.source_url"
        target="_blank"
        rel="noopener noreferrer"
        class="text-turn underline"
      >
        source
      </a>
      <a
        :href="reveal.page_url"
        target="_blank"
        rel="noopener noreferrer"
        class="text-turn underline"
      >
        on {{ booru }}
      </a>
    </div>

    <template v-if="over">
      <!-- The heading names the winner(s); the standings carry the full ranking,
           so a separate winners line would just repeat what's already shown. -->
      <ol class="divide-y divide-border rounded-lg border border-border bg-surface text-sm">
        <li
          v-for="(p, i) in over.standings"
          :key="p.uuid"
          class="flex items-center justify-between px-3 py-2"
        >
          <span class="flex items-center gap-2">
            <span
              ><span class="mr-2 font-mono text-ink-faint">{{ i + 1 }}.</span>{{ p.name }}</span
            >
            <span
              v-if="wins(p.uuid)"
              class="rounded-full bg-turn/10 px-1.5 text-xs font-semibold text-turn"
              :title="`${wins(p.uuid)} win${wins(p.uuid) === 1 ? '' : 's'} in this room`"
            >
              🏆 {{ wins(p.uuid) }}
            </span>
          </span>
          <span class="font-mono font-semibold tabular-nums">{{ p.score }}</span>
        </li>
      </ol>
    </template>

    <RoundSummary />

    <!-- Last in the section, so it floats over the whole tag recap and settles
         only at the very bottom: `sticky bottom` holds an element down only
         while its own place in the flow is still below the fold, and the recap
         runs long enough to bury anything it doesn't cover. -->
    <div
      class="sticky bottom-4 z-10 rounded-lg border border-border bg-surface p-3 shadow-lg shadow-black/20"
    >
      <ReadyBar start-label="Start next round" show-back @back="emit('back')" />
    </div>
  </section>
</template>

<style scoped>
/* Lands a beat after the panel, like a stamp. */
.sweep {
  animation: sweep-in 0.45s cubic-bezier(0.2, 1.4, 0.4, 1) 0.15s backwards;
}
@keyframes sweep-in {
  from {
    opacity: 0;
    transform: scale(0.8) rotate(-3deg);
  }
}
</style>
