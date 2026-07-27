<script setup lang="ts">
/**
 * Ready up and start, side by side — the one place a round begins. Readying and
 * starting are a single thought, so they live in a single control; the results
 * screen mounts this too, so a rematch never needs the lobby.
 */
import { computed } from 'vue'

import { allReady, readyLine } from '@/game/lobbyStatus'
import { errorLabel } from '@/lib/errors'
import { useRoomStore } from '@/stores/room'

withDefaults(defineProps<{ startLabel?: string; showBack?: boolean }>(), {
  startLabel: 'Start game',
  showBack: false,
})

const emit = defineEmits<{ back: [] }>()

const room = useRoomStore()

const ready = computed(() => room.me?.ready ?? false)
const everyoneReady = computed(() => allReady(room.users))

// One line for four things, because there's only room for one: what's blocking
// the start, or — once nothing is — who else is in for the next round.
const hint = computed(() => {
  if (room.starting) return 'Finding an image…'
  if (room.error) return errorLabel(room.error)
  const line = readyLine(room.users)
  if (ready.value) return line
  return line ? `Ready up to start · ${line}` : 'Ready up to start the game.'
})
</script>

<template>
  <div class="flex flex-col gap-2">
    <div class="flex flex-wrap items-center gap-2">
      <button
        class="shrink-0 rounded-lg px-4 py-2.5 text-sm font-semibold"
        :class="ready ? 'bg-correct text-on-accent' : 'border border-border hover:bg-raised'"
        @click="room.setReady(!ready)"
      >
        {{ ready ? 'Ready ✓' : 'Ready up' }}
      </button>
      <!-- Haloed once the room is waiting on nobody but the press. -->
      <button
        class="relative flex min-w-40 flex-1 items-center justify-center gap-2 rounded-lg bg-turn px-4 py-2.5 text-sm font-semibold text-on-accent disabled:opacity-40"
        :class="{ 'all-ready': everyoneReady && !room.starting }"
        :disabled="!ready || room.starting"
        @click="room.startGame()"
      >
        <span
          v-if="room.starting"
          class="h-4 w-4 animate-spin rounded-full border-2 border-on-accent/30 border-t-on-accent"
        />
        {{ room.starting ? 'Starting…' : startLabel }}
      </button>
      <!-- A full button, not a footnote: the settings live in the lobby, so
           going back is a routine move between rounds, not an escape hatch. -->
      <button
        v-if="showBack"
        class="shrink-0 rounded-lg border border-border px-4 py-2.5 text-sm font-semibold hover:bg-raised"
        @click="emit('back')"
      >
        ← Back to lobby
      </button>
    </div>
    <!-- Height reserved: the line empties when you ready up in a room of one,
         and everything below it used to jump when it did. -->
    <p
      class="min-h-4 text-xs leading-4"
      :class="room.error ? 'text-wrong' : 'text-ink-faint'"
      aria-live="polite"
    >
      {{ hint }}
    </p>
  </div>
</template>

<style scoped>
/* A tight ring and a bloom past it, breathed with opacity so the pulse stays
   on the compositor — a shadow that changes size instead re-rasterises a
   bigger region every frame, and flickers at the top of the cycle. Starting
   dim makes the first half-cycle the swell-in. */
.all-ready::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  box-shadow:
    0 0 0 2px color-mix(in srgb, var(--color-turn) 60%, transparent),
    0 0 26px 4px color-mix(in srgb, var(--color-turn) 60%, transparent);
  animation: all-ready-breathe 2.1s ease-in-out infinite alternate;
  will-change: opacity;
  pointer-events: none;
}

@keyframes all-ready-breathe {
  from {
    opacity: 0.3;
  }
  to {
    opacity: 1;
  }
}
</style>
