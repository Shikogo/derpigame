<script setup lang="ts">
/**
 * The live round's hero: the big pan/zoom image. The turn controls live beside
 * it in the rail (`GameControls`). Shows a "round in progress" placeholder for a
 * late joiner who has no game snapshot yet (see the deferred mid-game-join note).
 *
 * The stage takes whatever box it is given, edge to edge: `RoomView` owns the
 * height, so the shrinking-for-the-keyboard case and the floor under a stacked
 * layout are decided in one place.
 *
 * On desktop that box is the whole shell, with the rail and the guess box laid
 * over its right and bottom edges — so the stage holds itself clear of both.
 * Insetting here rather than sizing the box there is what lets a panel arrive or
 * leave without the furniture resizing whatever is mid-fade.
 *
 * Keep the template single-root — the two branches are one root, but a stray
 * comment or sibling beside them makes this a fragment, and `RoomView` wraps it
 * in a `<Transition mode="out-in">` that then has no element to animate: the
 * leave never resolves and the panel replacing it never appears.
 */
import { computed, ref } from 'vue'

import GuessOverlay from '@/components/GuessOverlay.vue'
import ImageViewer from '@/components/ImageViewer.vue'
import { useGameStore } from '@/stores/game'

const game = useGameStore()

// Having a picture is the whole test: it covers the live round, the `ending`
// outro, and the moment this panel spends fading out after the round is over.
// Keying off status instead would swap this component's root mid-fade, which
// pulls the element out from under the leave transition animating it.
const live = computed(() => !!game.state.image)

// The stage is the whole window, but the picture inside it is its own shape, so
// the overlay hangs in empty black unless it is told where the picture ends.
const viewer = ref<InstanceType<typeof ImageViewer> | null>(null)
const pictureBottom = computed(() => viewer.value?.contentBottom ?? 0)
</script>

<template>
  <div v-if="live" class="h-full min-h-0 w-full lg:pb-16 lg:pe-88">
    <!-- Haloed for as long as the room is waiting on you -->
    <section class="relative h-full w-full overflow-hidden" :class="{ 'my-turn': game.isMyTurn }">
      <ImageViewer ref="viewer" :src="game.state.image!.full_url" alt="Guess the tags" />
      <GuessOverlay :picture-bottom="pictureBottom" />
    </section>
  </div>

  <section v-else class="flex min-h-[45vh] flex-col items-center justify-center gap-2 text-center">
    <p class="font-display text-lg font-semibold">A round is already in progress.</p>
    <p class="text-sm text-ink-muted">You’ll join automatically when the next round starts.</p>
  </section>
</template>

<style scoped>
/* Inset because the panel clips: the `overflow-hidden` the picture needs would
   take an outer bloom with it. Breathed with opacity to keep the pulse on the
   compositor. */
.my-turn::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 1;
  border-radius: inherit;
  box-shadow:
    inset 0 0 0 2px color-mix(in srgb, var(--color-turn) 75%, transparent),
    inset 0 0 34px 6px color-mix(in srgb, var(--color-turn) 45%, transparent);
  animation: my-turn-breathe 2.1s ease-in-out infinite alternate;
  will-change: opacity;
  pointer-events: none;
}

@keyframes my-turn-breathe {
  from {
    opacity: 0.35;
  }
  to {
    opacity: 1;
  }
}
</style>
