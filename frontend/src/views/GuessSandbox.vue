<script setup lang="ts">
/**
 * Dev-only harness for `GuessOverlay`: an image with the overlay on top and
 * buttons that push fabricated `game_events` batches through the real store and
 * reducer, so the cards can be judged without a backend or a second player.
 * Not part of the game UI.
 */
import { onMounted } from 'vue'

import GuessOverlay from '@/components/GuessOverlay.vue'
import ImageViewer from '@/components/ImageViewer.vue'
import { useGameStore } from '@/stores/game'
import type { GameEvent, Player } from '@/types/wire'

const game = useGameStore()

const SHIKO: Player = { uuid: 'a', name: 'Shiko', score: 0, wrong_guesses: 0 }
const ARI: Player = { uuid: 'b', name: 'Ari', score: 0, wrong_guesses: 0 }

function player(base: Player, over: Partial<Player> = {}): Player {
  return { ...base, ...over }
}

function startRound(): void {
  game.reset()
  game.applyEvents([
    { type: 'image_started', id: 'sandbox', thumb_url: '', full_url: '/viewer-test.svg' },
    {
      type: 'game_started',
      first_player: SHIKO,
      players: [SHIKO, ARI],
      tag_count: 12,
      bonus_counts: { artists: 1, ocs: 2 },
      freebie_tags: ['pony', 'safe'],
      turn_seconds: 30,
      elimination_threshold: 3,
    },
  ])
}

function fire(...events: GameEvent[]): void {
  game.applyEvents(events)
}

const cases: { label: string; run: () => void }[] = [
  {
    label: 'Correct',
    run: () =>
      fire({
        type: 'correct_guess',
        player: player(SHIKO, { score: 1 }),
        guess: 'twilight sparkle',
        tag_type: 'tags',
        remaining: 11,
      }),
  },
  // The three shapes aliasing takes: a shared prefix, a shared suffix, and an
  // abbreviation sharing nothing real.
  {
    label: 'Alias · expansion',
    run: () =>
      fire({
        type: 'correct_guess',
        player: player(SHIKO, { score: 2 }),
        guess: 'twilight sparkle',
        tag_type: 'tags',
        remaining: 10,
        as_typed: 'twilight',
      }),
  },
  {
    label: 'Alias · abbreviation',
    run: () =>
      fire({
        type: 'correct_guess',
        player: player(SHIKO, { score: 3 }),
        guess: 'twilight sparkle',
        tag_type: 'tags',
        remaining: 9,
        as_typed: 'ts',
      }),
  },
  {
    label: 'Alias · namespace (bonus)',
    run: () =>
      fire({
        type: 'correct_guess',
        player: player(ARI, { score: 1 }),
        guess: 'artist:shikogo',
        tag_type: 'artists',
        remaining: 0,
        as_typed: 'shikogo',
      }),
  },
  {
    label: 'Near miss',
    run: () =>
      fire({
        type: 'near_miss',
        player: player(SHIKO),
        guess: 'twilite sparkle',
        closeness: 92,
      }),
  },
  {
    label: 'Wrong · strike 1',
    run: () =>
      fire({
        type: 'wrong_guess',
        player: player(ARI, { wrong_guesses: 1 }),
        guess: 'rainbow dash',
        wrong_count: 1,
      }),
  },
  {
    label: 'Wrong · strike 2',
    run: () =>
      fire({
        type: 'wrong_guess',
        player: player(ARI, { wrong_guesses: 2 }),
        guess: 'applejack',
        wrong_count: 2,
      }),
  },
  {
    label: 'Wrong · strike 3 → out',
    run: () =>
      fire(
        {
          type: 'wrong_guess',
          player: player(ARI, { wrong_guesses: 3 }),
          guess: 'fluttershy',
          wrong_count: 3,
        },
        { type: 'player_eliminated', player: player(ARI, { wrong_guesses: 3 }) },
      ),
  },
  {
    label: 'Timeout',
    run: () =>
      fire({
        type: 'timeout',
        player: player(SHIKO, { wrong_guesses: 1 }),
        wrong_count: 1,
      }),
  },
  {
    label: 'Rejected',
    run: () => fire({ type: 'guess_rejected', guess: 'safe', reason: 'rating_tag' }),
  },
  {
    label: 'Burst ×5',
    run: () =>
      fire(
        {
          type: 'correct_guess',
          player: player(SHIKO, { score: 3 }),
          guess: 'unicorn',
          tag_type: 'tags',
          remaining: 9,
        },
        { type: 'near_miss', player: player(ARI), guess: 'magik', closeness: 88 },
        {
          type: 'wrong_guess',
          player: player(ARI, { wrong_guesses: 1 }),
          guess: 'pinkie pie',
          wrong_count: 1,
        },
        {
          type: 'correct_guess',
          player: player(SHIKO, { score: 4 }),
          guess: 'oc:littlepip',
          tag_type: 'ocs',
          remaining: 1,
          as_typed: 'littlepip',
        },
        { type: 'guess_rejected', guess: 'unicorn', reason: 'already_guessed' },
      ),
  },
]

onMounted(startRound)
</script>

<template>
  <main class="mx-auto flex max-w-4xl flex-col gap-4 p-6">
    <header class="flex items-center justify-between">
      <h1 class="font-display text-xl font-bold">GuessOverlay sandbox</h1>
      <button
        class="rounded bg-turn px-3 py-1.5 text-sm font-medium text-on-accent"
        @click="startRound"
      >
        Reset round
      </button>
    </header>

    <p class="text-sm text-ink-muted">
      Each button pushes a real <code class="font-mono text-xs">game_events</code> batch through the
      store, so what renders is the production data path minus the socket.
    </p>

    <div class="relative h-[520px] w-full overflow-hidden rounded-xl border border-border">
      <ImageViewer src="/viewer-test.svg" alt="Sandbox image" />
      <GuessOverlay />
    </div>

    <div class="flex flex-wrap gap-2">
      <button
        v-for="c in cases"
        :key="c.label"
        class="rounded-lg border border-border bg-raised px-3 py-1.5 text-xs font-medium text-ink hover:border-turn hover:text-turn"
        @click="c.run()"
      >
        {{ c.label }}
      </button>
    </div>

    <p class="text-xs text-ink-faint">
      Feed entries: {{ game.state.feed.length }} · strike limit: {{ game.state.strikeLimit }}
    </p>
  </main>
</template>
