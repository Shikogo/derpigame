<script setup lang="ts">
/**
 * The card for a landing guess, pinned to the bottom of the picture just over
 * the guess box: who guessed, what they guessed (and what they typed, if the
 * server translated it), the verdict, and the strikes it cost. Rises, holds,
 * fades — the result lands where the typing happens.
 *
 * Cards are queued rather than latched to the newest entry, because one
 * `applyEvents` batch can carry several and showing only the last would drop
 * the rest. A backed-up queue shortens the hold instead of stacking cards over
 * the picture, which is the thing everyone is actually looking at.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { overlayCards, type CardTone, type OverlayCard } from '@/game/overlay'
import { bucketPillStyle } from '@/lib/tagColor'
import { useGameStore } from '@/stores/game'

const HOLD_MS = 1500 // long enough to read; the strip sits clear of the subject
const HOLD_BUSY_MS = 700 // catching up, so each card gets a glance not a dwell
const GAP_MS = 180 // lets the leave transition finish before the next enters
const MAX_QUEUE = 3 // a burst shows the most recent few, never a backlog

// Height of the letterbox band under the picture: the card is lifted by it to
// clear the picture's bottom edge. 0 (the default, for a caller with no viewer
// to ask) leaves the card over the picture, which is also where a band too short
// to hold it puts it.
const props = withDefaults(defineProps<{ pictureBottom?: number }>(), { pictureBottom: 0 })

const game = useGameStore()

const queue = ref<OverlayCard[]>([])
const current = ref<OverlayCard | null>(null)
let seen = 0
let timer: ReturnType<typeof setTimeout> | undefined

const TONE: Record<CardTone, { text: string; ring: string; glow: string }> = {
  correct: { text: 'text-correct', ring: 'ring-correct/40', glow: 'shadow-correct/25' },
  wrong: { text: 'text-wrong', ring: 'ring-wrong/40', glow: 'shadow-wrong/25' },
  near: { text: 'text-very-close', ring: 'ring-very-close/40', glow: 'shadow-very-close/25' },
  out: { text: 'text-eliminated', ring: 'ring-eliminated/50', glow: 'shadow-eliminated/25' },
  muted: { text: 'text-white/55', ring: 'ring-white/15', glow: 'shadow-black/25' },
}

const tone = computed(() => TONE[current.value?.tone ?? 'muted'])
const bonusKeys = computed(() => Object.keys(game.state.bonusCounts))

// Newest first: the entries added since the last pass, mapped to cards.
watch(
  () => game.state.feed,
  (feed) => {
    if (!feed.length || feed[feed.length - 1].seq <= seen) return
    const cards = overlayCards(feed, game.state.strikeLimit, seen)
    seen = feed[feed.length - 1].seq
    if (cards.length) queue.value = [...queue.value, ...cards].slice(-MAX_QUEUE)
    // Pumped even with nothing added: a batch whose only new entry was dropped
    // still has to let a round that's waiting on the outro finish.
    pump()
  },
  { deep: false },
)

// A fresh round rewinds the feed, so the watermark has to rewind with it or the
// new round's first guesses look stale and never show.
watch(
  () => game.state.image?.id,
  () => {
    seen = 0
    queue.value = []
    current.value = null
    clearTimeout(timer)
  },
)

function pump(): void {
  if (current.value) return
  if (!queue.value.length) {
    // Nothing left to show. If the round is only waiting on this outro to
    // finish, that's now — which is what lets clicking through the last cards
    // reach the results early instead of sitting out a fixed delay.
    game.finishRound()
    return
  }
  const [next, ...rest] = queue.value
  queue.value = rest
  current.value = next
  timer = setTimeout(retire, queue.value.length ? HOLD_BUSY_MS : HOLD_MS)
}

function retire(): void {
  current.value = null
  timer = setTimeout(pump, GAP_MS)
}

/**
 * Any pointer press clears the card early — the moment you reach for the
 * picture, the thing on top of it should get out of the way. A queued card
 * still follows, so a burst can be clicked through rather than waited out.
 *
 * Listening on the window rather than the card keeps the overlay
 * `pointer-events-none`: making the card itself the target would put a dead
 * zone for panning over the middle of the image.
 */
function dismiss(event: PointerEvent): void {
  if (!current.value) return
  // On a phone the guess box sits inches under the picture. Reaching for the
  // keyboard isn't "get out of the way" — reaching for the picture is.
  if (event.target instanceof Element && event.target.closest('[data-guess-dock]')) return
  clearTimeout(timer)
  retire()
}

onMounted(() => window.addEventListener('pointerdown', dismiss))

onBeforeUnmount(() => {
  clearTimeout(timer)
  window.removeEventListener('pointerdown', dismiss)
})
</script>

<template>
  <!-- The card attaches to the bottom edge of the picture from the outside: this
       div is the letterbox band, pinned to the foot of the frame, and the card
       sits at its top — just clear of the picture. A booru image's subject sits
       dead centre, so covering any of it is a last resort, and `min-h-min` is
       what makes it one: a band too short to hold the card grows to fit it, and
       since the band is pinned by its bottom it grows up over the picture rather
       than off-frame. pointer-events-none throughout, so the picture stays
       pannable.

       The card is one row on a wide picture and wraps to two on a phone, where
       truncating would eat the headline — the one part worth reading. -->
  <div
    class="pointer-events-none absolute inset-x-0 bottom-0 z-10 grid min-h-min content-start justify-center p-2 transition-[height] duration-200 sm:p-3"
    :style="{ height: `${props.pictureBottom}px` }"
  >
    <Transition name="card">
      <div
        v-if="current"
        :key="current.seq"
        class="flex max-w-full flex-wrap items-center justify-center gap-x-2.5 gap-y-1 rounded-xl bg-black/70 px-3 py-2 shadow-xl ring-1 backdrop-blur-md sm:flex-nowrap sm:gap-3 sm:px-4 sm:py-2.5"
        :class="[tone.ring, tone.glow]"
        role="status"
        aria-live="polite"
      >
        <!-- verdict badge -->
        <span
          class="grid h-7 w-7 shrink-0 place-items-center rounded-full ring-2 sm:h-8 sm:w-8"
          :class="[tone.text, tone.ring]"
        >
          <svg
            class="h-4 w-4 sm:h-5 sm:w-5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="3"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path v-if="current.tone === 'correct'" d="M4 12.5 9.5 18 20 7" />
            <path
              v-else-if="current.tone === 'near'"
              d="M3 9c3-3 5 3 8 0s5-3 8 0M3 16c3-3 5 3 8 0s5-3 8 0"
            />
            <path v-else-if="current.tone === 'muted'" d="M5 12h14" />
            <path v-else d="m5 5 14 14M19 5 5 19" />
          </svg>
        </span>

        <span
          v-if="current.player"
          class="shrink-0 text-xs font-semibold uppercase tracking-[0.14em]"
          :class="tone.text"
          >{{ current.player }}</span
        >

        <!-- A translated guess keeps the player's own wording, now inline: the
             strip reads left to right, so the arrow points that way too. -->
        <span class="flex min-w-0 items-baseline gap-1.5">
          <span
            v-if="current.asTyped"
            class="shrink-0 font-display text-xs font-semibold text-white/45"
            >{{ current.asTyped }}<span aria-hidden="true" class="text-white/30"> →</span></span
          >
          <span class="truncate font-display text-base font-bold text-white sm:text-xl">{{
            current.headline
          }}</span>
        </span>

        <!-- strikes: one X per strike actually taken, never padded to the limit -->
        <div v-if="current.strikes" class="flex shrink-0 items-center gap-1" :class="tone.text">
          <svg
            v-for="n in current.strikes.used"
            :key="n"
            class="strike h-4 w-4 sm:h-5 sm:w-5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="3.5"
            stroke-linecap="round"
            :style="{ animationDelay: `${100 + (n - 1) * 90}ms` }"
          >
            <path d="m5 5 14 14M19 5 5 19" />
          </svg>
        </div>

        <span
          v-if="current.bucket"
          class="pill shrink-0"
          :style="bucketPillStyle(current.bucket, bonusKeys)"
        >
          {{ current.bucket }} · {{ current.detail }}
        </span>
        <span v-else-if="current.detail" class="shrink-0 text-xs text-white/60">{{
          current.detail
        }}</span>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* Enter and leave share the one grid cell, so a leaving card can't shove the
   next one off-centre and neither needs taking out of flow. */
.card-enter-active,
.card-leave-active {
  grid-column: 1;
  grid-row: 1;
}
.card-enter-active {
  transition:
    opacity 0.16s ease-out,
    transform 0.16s cubic-bezier(0.2, 1.5, 0.4, 1);
}
.card-leave-active {
  transition:
    opacity 0.22s ease-in,
    transform 0.22s ease-in;
}
/* Up off the guess box, the way the guess itself went. */
.card-enter-from {
  opacity: 0;
  transform: translateY(10px) scale(0.9);
}
.card-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(1.02);
}

/* Each X lands a beat after the card, so the strike reads as its own event. */
.strike {
  animation: strike-in 0.24s cubic-bezier(0.2, 1.5, 0.4, 1) backwards;
}
@keyframes strike-in {
  from {
    opacity: 0;
    transform: scale(1.9) rotate(-18deg);
  }
}
</style>
