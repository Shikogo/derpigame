<script setup lang="ts">
/** Room roster with where each member is, and their running win count. */
import { presenceOf } from '@/game/lobbyStatus'
import { useRoomStore } from '@/stores/room'
import { useSessionStore } from '@/stores/session'

const room = useRoomStore()
const session = useSessionStore()

const LABELS = { ready: 'Ready', results: 'On results', lobby: 'In lobby' } as const
const TONES = {
  ready: 'text-correct',
  results: 'text-ink-muted',
  lobby: 'text-ink-faint',
} as const
</script>

<template>
  <ul class="divide-y divide-border rounded-lg border border-border bg-surface">
    <li
      v-for="u in room.usersWithWins"
      :key="u.uuid"
      class="flex items-center justify-between px-3 py-2 text-sm"
    >
      <span class="flex items-center gap-2">
        <span class="font-medium">{{ u.name }}</span>
        <span v-if="u.uuid === session.uuid" class="text-xs text-ink-faint">(you)</span>
        <span
          v-if="u.wins"
          class="rounded-full bg-turn/10 px-1.5 text-xs font-semibold text-turn"
          :title="`${u.wins} win${u.wins === 1 ? '' : 's'}`"
        >
          🏆 {{ u.wins }}
        </span>
      </span>
      <span
        class="text-xs font-semibold"
        :class="TONES[presenceOf(u)]"
        :title="presenceOf(u) === 'results' ? 'Still reading the last round’s results' : undefined"
      >
        {{ LABELS[presenceOf(u)] }}
      </span>
    </li>
  </ul>
</template>
