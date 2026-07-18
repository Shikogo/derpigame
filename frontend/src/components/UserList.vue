<script setup lang="ts">
/** Room roster with ready state and each player's running win count. */
import { useRoomStore } from '@/stores/room'
import { useSessionStore } from '@/stores/session'

const room = useRoomStore()
const session = useSessionStore()
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
      <span class="text-xs font-semibold" :class="u.ready ? 'text-correct' : 'text-ink-faint'">
        {{ u.ready ? 'Ready' : 'Not ready' }}
      </span>
    </li>
  </ul>
</template>
