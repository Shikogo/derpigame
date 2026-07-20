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
        class="flex items-center justify-between px-3 py-2 text-sm"
        :class="{ 'bg-turn/5': isActive(p.uuid), 'opacity-50': isEliminated(p.uuid) }"
      >
        <span class="flex items-center gap-2">
          <span
            v-if="isActive(p.uuid)"
            class="h-2 w-2 rounded-full bg-turn"
            title="Active player"
          />
          <span class="font-medium" :class="{ 'line-through': isEliminated(p.uuid) }">
            {{ p.name }}
          </span>
        </span>
        <span class="flex items-center gap-3 font-mono tabular-nums">
          <span class="font-semibold">{{ p.score }}</span>
          <span v-if="p.wrong_guesses" class="text-xs text-wrong">✗{{ p.wrong_guesses }}</span>
        </span>
      </li>
    </ul>
    <p v-if="room.spectatorCount" class="border-t border-border px-3 py-1.5 text-xs text-ink-faint">
      {{ room.spectatorCount }} spectator{{ room.spectatorCount === 1 ? '' : 's' }}
    </p>
  </div>
</template>
