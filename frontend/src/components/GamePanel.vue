<script setup lang="ts">
/**
 * The live round's hero: the big pan/zoom image. The turn controls live beside
 * it in the rail (`GameControls`). Shows a "round in progress" placeholder for a
 * late joiner who has no game snapshot yet (see the deferred mid-game-join note).
 *
 * On desktop the viewer fills the viewport height (minus the app header/pad);
 * the rail matches it via the grid row. Elsewhere it takes whatever height the
 * cell gives it — `RoomView` owns that, so the shrinking-for-the-keyboard case
 * and the floor under a stacked layout are decided in one place.
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

// The viewer fills the panel, but the picture inside it doesn't: on a tall
// screen a fitted image leaves a wide letterbox band, and the overlay hangs in
// empty black unless it's told where the picture starts.
const viewer = ref<InstanceType<typeof ImageViewer> | null>(null)
const pictureTop = computed(() => viewer.value?.contentTop ?? 0)
</script>

<template>
  <!-- Haloed for as long as the room is waiting on you -->
  <section
    v-if="live"
    class="relative overflow-hidden rounded-xl ring-1 ring-turn/20 shadow-[0_0_70px_-24px_rgba(79,157,255,0.6)] max-lg:rounded-none max-lg:shadow-none max-lg:ring-0 lg:h-[calc(100dvh_-_5.5rem)] lg:min-h-0"
    :class="{ 'my-turn': game.isMyTurn }"
  >
    <ImageViewer ref="viewer" :src="game.state.image!.full_url" alt="Guess the tags" />
    <GuessOverlay :picture-top="pictureTop" />
  </section>

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
