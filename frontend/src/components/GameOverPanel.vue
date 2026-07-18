<script setup lang="ts">
/**
 * End-of-round screen for both a finished game and an aborted one. Either way it
 * reveals the image attribution (artist + source/derpibooru links); a finished
 * game also shows winners, standings, and the tags nobody got.
 */
import { computed } from 'vue'

import { useGameStore } from '@/stores/game'
import { useSessionStore } from '@/stores/session'

const emit = defineEmits<{ back: [] }>()

const game = useGameStore()
const session = useSessionStore()

const aborted = computed(() => game.state.status === 'aborted')
const over = computed(() => game.state.over)
const reveal = computed(() => game.state.reveal)
const image = computed(() => game.state.image)
const iWon = computed(() => over.value?.winners.some((w) => w.uuid === session.uuid) ?? false)

const heading = computed(() => {
  if (aborted.value) return 'Round stopped'
  if (iWon.value) return 'You won! 🎉'
  return over.value?.win ? 'Round over' : 'Nobody got them all'
})
</script>

<template>
  <section class="mx-auto flex w-full max-w-3xl flex-col gap-5">
    <h2 class="text-2xl font-bold" :class="iWon ? 'text-correct' : 'text-turn'">{{ heading }}</h2>

    <div v-if="image" class="overflow-hidden rounded-lg border border-gray-200">
      <img
        :src="image.full_url"
        alt="The revealed image"
        class="max-h-[50vh] w-full bg-black/80 object-contain"
      />
    </div>

    <div v-if="reveal" class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
      <span v-if="reveal.artists.length" class="font-medium">by {{ reveal.artists.join(', ') }}</span>
      <span v-else class="text-gray-400">artist unknown</span>
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
        on derpibooru
      </a>
    </div>

    <template v-if="over">
      <p v-if="over.winners.length" class="text-sm">
        <span class="font-semibold">Winner{{ over.winners.length > 1 ? 's' : '' }}:</span>
        {{ over.winners.map((w) => w.name).join(', ') }}
      </p>
      <ol class="divide-y divide-gray-100 rounded-lg border border-gray-200 text-sm">
        <li
          v-for="(p, i) in over.standings"
          :key="p.uuid"
          class="flex items-center justify-between px-3 py-2"
        >
          <span><span class="mr-2 text-gray-400">{{ i + 1 }}.</span>{{ p.name }}</span>
          <span class="font-semibold tabular-nums">{{ p.score }}</span>
        </li>
      </ol>
      <p v-if="over.unguessed_tags.length" class="text-sm">
        <span class="font-semibold text-wrong">Missed:</span>
        <span class="text-gray-600"> {{ over.unguessed_tags.join(', ') }}</span>
      </p>
    </template>

    <button
      class="self-start rounded-lg bg-turn px-4 py-2 text-sm font-semibold text-white"
      @click="emit('back')"
    >
      Back to lobby
    </button>
  </section>
</template>
