<script setup lang="ts">
/**
 * Between-rounds recap: the win leaderboard and a list of past rounds (each
 * links to its derpibooru page). Both come straight from the room snapshot.
 */
import { computed } from 'vue'

import { useRoomStore } from '@/stores/room'

const room = useRoomStore()

// Newest round first; the snapshot stores them oldest-first.
const rounds = computed(() => [...room.history].reverse())
</script>

<template>
  <section v-if="rounds.length || room.winCounts.length" class="flex flex-col gap-3">
    <div v-if="room.winCounts.length">
      <h3 class="mb-1.5 text-sm font-semibold text-gray-600">Wins</h3>
      <ol class="flex flex-wrap gap-2">
        <li
          v-for="(w, i) in room.winCounts"
          :key="w.uuid"
          class="rounded-full bg-turn/10 px-2.5 py-1 text-xs font-medium text-turn"
        >
          {{ i + 1 }}. {{ w.name }} — {{ w.wins }} win{{ w.wins === 1 ? '' : 's' }}
        </li>
      </ol>
    </div>

    <div v-if="rounds.length">
      <h3 class="mb-1.5 text-sm font-semibold text-gray-600">Past rounds</h3>
      <ul class="flex flex-col gap-2">
        <li
          v-for="(r, i) in rounds"
          :key="i"
          class="flex items-center gap-3 rounded-lg border border-gray-200 p-2 text-sm"
        >
          <a :href="r.page_url" target="_blank" rel="noopener noreferrer" class="shrink-0">
            <img :src="r.thumb_url" alt="round image" class="h-12 w-12 rounded object-cover" />
          </a>
          <div class="min-w-0 flex-1">
            <p class="truncate">
              <span v-if="r.aborted" class="text-gray-400">Stopped</span>
              <span v-else-if="r.winners.length" class="text-correct">
                Won by {{ r.winners.map((w) => w.name).join(', ') }}
              </span>
              <span v-else class="text-wrong">No winner</span>
            </p>
            <p v-if="r.artists.length" class="truncate text-xs text-gray-400">
              by {{ r.artists.join(', ') }}
            </p>
          </div>
        </li>
      </ul>
    </div>
  </section>
</template>
