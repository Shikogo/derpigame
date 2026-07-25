<script setup lang="ts">
/**
 * Dev-only harness for `ConfettiOverlay`: fires any celebration on demand and
 * puts every tuning knob on a slider, so the feel can be dialled in without
 * editing constants and reloading. Not part of the game UI.
 *
 * Every knob applies to the next shot — `canvas-confetti` reads its options once
 * when a burst goes up and animates it from there.
 */
import { computed, reactive, ref } from 'vue'

import ConfettiOverlay from '@/components/ConfettiOverlay.vue'
import { DEFAULT_TUNING, type CelebrationKind, type ConfettiTuning } from '@/lib/confetti'
import { useFrameRate } from '@/views/sandbox/useFrameRate'

// The overlay is mounted idle and fired imperatively, so shots stack — mash the
// buttons and the paper piles up instead of each click wiping the last.
const confetti = ref<InstanceType<typeof ConfettiOverlay> | null>(null)
const shots = ref(0)

const tuning = reactive<ConfettiTuning>({ ...DEFAULT_TUNING })

interface Knob {
  key: keyof ConfettiTuning
  label: string
  min: number
  max: number
  step: number
  hint: string
}

const VOLLEY: Knob[] = [
  { key: 'particleCount', label: 'Count', min: 10, max: 250, step: 5, hint: 'pieces per barrel' },
  { key: 'spread', label: 'Spread', min: 5, max: 180, step: 5, hint: 'cone width, degrees' },
  { key: 'startVelocity', label: 'Velocity', min: 10, max: 120, step: 2, hint: 'launch speed' },
  { key: 'scalar', label: 'Scale', min: 0.4, max: 3, step: 0.1, hint: 'paper size' },
]

const FLIGHT: Knob[] = [
  { key: 'gravity', label: 'Gravity', min: 0, max: 3, step: 0.05, hint: 'pull down' },
  { key: 'decay', label: 'Decay', min: 0.8, max: 0.99, step: 0.005, hint: 'speed kept per frame' },
  { key: 'ticks', label: 'Ticks', min: 50, max: 600, step: 10, hint: 'lifetime, frames' },
]

const changed = computed(() =>
  (Object.keys(DEFAULT_TUNING) as (keyof ConfettiTuning)[]).filter(
    (k) => tuning[k] !== DEFAULT_TUNING[k],
  ),
)

/** The current values as a paste-ready `DEFAULT_TUNING` body. */
const snippet = computed(() =>
  (Object.keys(DEFAULT_TUNING) as (keyof ConfettiTuning)[])
    .map((k) => `  ${k}: ${tuning[k]},`)
    .join('\n'),
)

const copied = ref(false)
async function copySnippet(): Promise<void> {
  await navigator.clipboard.writeText(
    `export const DEFAULT_TUNING: ConfettiTuning = {\n${snippet.value}\n}`,
  )
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}

function reset(): void {
  Object.assign(tuning, DEFAULT_TUNING)
}

// Frame rate while the paper flies, sampled independently of the overlay — the
// point of this harness is judging whether a heavy volley still runs smooth.
const { fps, worst, janky, watch, reset: resetFrames } = useFrameRate()

function fire(...kinds: CelebrationKind[]): void {
  confetti.value?.fire(kinds)
  shots.value++
  watch()
}

/** Clears the run's stats, not the tuning — the worst frame is a spam record. */
function resetStats(): void {
  shots.value = 0
  resetFrames()
}
</script>

<template>
  <main class="mx-auto flex max-w-3xl flex-col gap-5 p-6">
    <header class="flex flex-wrap items-baseline justify-between gap-3">
      <h1 class="font-display text-xl font-bold">Confetti sandbox</h1>
      <!-- Fixed width, so the changing digits don't jog the header around. -->
      <p
        v-if="shots"
        class="w-72 shrink-0 text-right font-mono text-xs text-ink-faint tabular-nums"
      >
        {{ shots }} shots · {{ fps }} fps · worst {{ worst }}ms · {{ janky }} janky
        <button class="ml-1 underline hover:text-ink" @click="resetStats">clear</button>
      </p>
    </header>

    <p class="text-sm text-ink-muted">
      Two things get celebrated, separately or together: the
      <strong class="text-ink">cannons</strong> are for taking the round, the
      <strong class="text-ink">fireworks</strong> for the room clearing every goal tag. Win the
      round the room swept and you get both.
    </p>

    <div class="flex flex-wrap items-center gap-2">
      <button
        class="rounded-lg bg-turn px-3 py-1.5 text-sm font-semibold text-on-accent"
        @click="fire('winner')"
      >
        Win
      </button>
      <button
        class="rounded-lg border border-correct bg-correct/10 px-3 py-1.5 text-sm font-semibold text-correct"
        @click="fire('sweep')"
      >
        Sweep
      </button>
      <button
        class="rounded-lg border border-turn bg-turn/10 px-3 py-1.5 text-sm font-semibold text-turn"
        @click="fire('winner', 'sweep')"
      >
        Win + sweep
      </button>
      <button
        class="rounded-lg border border-border px-3 py-1.5 text-sm text-ink-muted hover:text-ink"
        :disabled="!changed.length"
        :class="{ 'opacity-40': !changed.length }"
        @click="reset"
      >
        Reset
      </button>
      <span v-if="changed.length" class="text-xs text-ink-faint">
        {{ changed.length }} changed from default
      </span>
    </div>

    <div class="grid gap-6 sm:grid-cols-2">
      <section
        v-for="group in [
          { title: 'Volley', note: 'applies on the next shot', knobs: VOLLEY },
          { title: 'Flight', note: 'applies on the next shot', knobs: FLIGHT },
        ]"
        :key="group.title"
        class="flex flex-col gap-3"
      >
        <h2 class="text-sm font-semibold">
          {{ group.title }}
          <span class="font-normal text-ink-faint">— {{ group.note }}</span>
        </h2>
        <label v-for="knob in group.knobs" :key="knob.key" class="flex flex-col gap-1">
          <span class="flex items-baseline justify-between text-xs">
            <span class="font-medium">{{ knob.label }}</span>
            <span class="font-mono text-ink-faint tabular-nums">{{ tuning[knob.key] }}</span>
          </span>
          <input
            v-model.number="tuning[knob.key]"
            type="range"
            :min="knob.min"
            :max="knob.max"
            :step="knob.step"
            class="accent-turn"
          />
          <span class="text-xs text-ink-faint">{{ knob.hint }}</span>
        </label>
      </section>
    </div>

    <section class="flex flex-col gap-2">
      <div class="flex items-center gap-2">
        <h2 class="text-sm font-semibold">Current tuning</h2>
        <button
          class="rounded border border-border px-2 py-0.5 text-xs text-ink-muted hover:text-ink"
          @click="copySnippet"
        >
          {{ copied ? 'Copied' : 'Copy' }}
        </button>
      </div>
      <pre
        class="overflow-x-auto rounded-lg border border-border bg-surface p-3 font-mono text-xs text-ink-muted"
        >{{ snippet }}</pre>
    </section>

    <p class="text-xs text-ink-faint">
      Reduced-motion viewers get nothing here — that's the overlay opting out, not a bug.
    </p>

    <ConfettiOverlay ref="confetti" :tuning="tuning" />
  </main>
</template>
