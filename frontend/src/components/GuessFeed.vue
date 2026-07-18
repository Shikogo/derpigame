<script setup lang="ts">
/** The ordered guess feed as colored badges, newest first. */
import { computed } from 'vue'

import type { FeedEntry } from '@/game/reducer'
import { useGameStore } from '@/stores/game'
import type { RejectReason } from '@/types/wire'

const game = useGameStore()

const badge = 'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium'

const REJECT: Record<RejectReason, string> = {
  already_guessed: 'already found',
  already_wrong: 'already tried',
  default_tag: 'freebie tag',
  rating_tag: 'rating tag',
}

// Precompute tone + text per entry so the template avoids union narrowing.
function describe(e: FeedEntry): { tone: string; text: string } {
  switch (e.kind) {
    case 'correct':
      return { tone: 'bg-correct/10 text-correct', text: `${e.player}: ${e.guess} · ${e.tag_type}` }
    case 'wrong':
      return {
        tone: 'bg-wrong/10 text-wrong',
        text: `${e.player}: ${e.guess}${e.closeness ? ` · ${e.closeness}%` : ''}`,
      }
    case 'timeout':
      return { tone: 'bg-eliminated/10 text-eliminated', text: `${e.player} timed out` }
    case 'eliminated':
      return { tone: 'bg-eliminated/10 text-eliminated', text: `${e.player} eliminated` }
    case 'rejected':
      return { tone: 'bg-gray-100 text-gray-500', text: `${e.guess} — ${REJECT[e.reason]}` }
  }
}

const items = computed(() =>
  [...game.state.feed].reverse().map((e) => ({ seq: e.seq, ...describe(e) })),
)
</script>

<template>
  <div class="flex flex-wrap gap-1.5">
    <span v-for="item in items" :key="item.seq" :class="[badge, item.tone]">{{ item.text }}</span>
    <p v-if="!items.length" class="text-xs text-gray-400">No guesses yet.</p>
  </div>
</template>
