<script setup lang="ts">
/** Live scores, highest first; marks the active player and the eliminated. */
import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'

const game = useGameStore()
const room = useRoomStore()

const isActive = (uuid: string) => game.activePlayer?.uuid === uuid
const isEliminated = (uuid: string) => game.state.eliminated.includes(uuid)
</script>

<template>
  <div class="overflow-hidden rounded-lg border border-border bg-surface">
    <ul class="divide-y divide-border">
      <li
        v-for="p in game.scoreboard"
        :key="p.uuid"
        class="flex items-center gap-3 px-3 py-2 text-sm"
        :class="{ 'bg-turn/5': isActive(p.uuid), 'opacity-50': isEliminated(p.uuid) }"
      >
        <!-- The turn marker keeps its slot on every row, so names don't step
             sideways as the turn moves down the list. -->
        <span
          class="h-2 w-2 shrink-0 rounded-full"
          :class="isActive(p.uuid) ? 'bg-turn' : 'bg-transparent'"
          :title="isActive(p.uuid) ? 'Active player' : undefined"
        />
        <span
          class="min-w-0 flex-1 truncate font-medium"
          :class="{ 'line-through': isEliminated(p.uuid) }"
        >
          {{ p.name }}
        </span>
        <!-- Every strike the round allows, spent ones filled in. Drawing the
             whole set keeps this column one width, so the scores line up
             whether or not anyone has missed yet. -->
        <span
          class="flex shrink-0 items-center gap-1"
          role="img"
          :aria-label="`${p.wrong_guesses} of ${game.state.strikeLimit} strikes`"
        >
          <svg
            v-for="n in game.state.strikeLimit"
            :key="n"
            class="h-3.5 w-3.5"
            :class="n <= p.wrong_guesses ? 'spent text-wrong' : 'text-ink-faint/30'"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="3.5"
            stroke-linecap="round"
            aria-hidden="true"
          >
            <path d="m5 5 14 14M19 5 5 19" />
          </svg>
        </span>
        <span class="shrink-0 font-mono font-semibold tabular-nums">{{ p.score }}</span>
      </li>
    </ul>
    <p v-if="room.spectatorCount" class="border-t border-border px-3 py-1.5 text-xs text-ink-faint">
      {{ room.spectatorCount }} spectator{{ room.spectatorCount === 1 ? '' : 's' }}
    </p>
  </div>
</template>

<style scoped>
/* A strike lands here the way it lands on the overlay card, so the two read as
   the same event. Fires once, when the cross goes from grey to spent. */
.spent {
  animation: strike-in 0.24s cubic-bezier(0.2, 1.5, 0.4, 1);
}
@keyframes strike-in {
  from {
    opacity: 0;
    transform: scale(1.9) rotate(-18deg);
  }
}
</style>
