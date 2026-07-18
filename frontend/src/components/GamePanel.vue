<script setup lang="ts">
/**
 * The live round's hero: the big pan/zoom image. The turn controls live beside
 * it in the rail (`GameControls`). Shows a "round in progress" placeholder for a
 * late joiner who has no game snapshot yet (see the deferred mid-game-join note).
 */
import { computed } from 'vue'

import ImageViewer from '@/components/ImageViewer.vue'
import { useGameStore } from '@/stores/game'

const game = useGameStore()

const live = computed(() => game.state.status === 'active' && !!game.state.image)
</script>

<template>
  <!-- On desktop the viewer fills the viewport height (minus the app header/pad);
       the rail matches it via the grid row. -->
  <section
    v-if="live"
    class="min-h-[50vh] overflow-hidden rounded-xl ring-1 ring-turn/20 shadow-[0_0_70px_-24px_rgba(79,157,255,0.6)] lg:h-[calc(100dvh_-_5.5rem)] lg:min-h-0"
  >
    <ImageViewer :src="game.state.image!.full_url" alt="Guess the tags" />
  </section>

  <section v-else class="flex min-h-[45vh] flex-col items-center justify-center gap-2 text-center">
    <p class="font-display text-lg font-semibold">A round is already in progress.</p>
    <p class="text-sm text-ink-muted">You’ll join automatically when the next round starts.</p>
  </section>
</template>
