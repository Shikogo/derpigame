<script setup lang="ts">
/**
 * Dev-only harness for the real room layout: seeds the stores so `RoomView`
 * renders without a backend, then pushes fabricated `game_events` batches
 * through the real store and reducer.
 *
 * The point is the things that only misbehave in the game's own layout — the
 * panel cross-fade into the results screen, and the confetti riding on top of
 * it. The sandboxes that mount a component on a bare page can't show those.
 */
import { computed, ref } from 'vue'

import RoomView from '@/views/RoomView.vue'
import { RIVAL, devRoomState, roundAborted, roundInPlay, roundWon } from '@/views/sandbox/fixtures'
import { useFrameRate } from '@/views/sandbox/useFrameRate'
import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'
import { useSessionStore } from '@/stores/session'
import type { Player } from '@/types/wire'

const room = useRoomStore()
const game = useGameStore()
const session = useSessionStore()

const ME: Player = {
  uuid: session.uuid,
  name: session.name || 'You',
  score: 7,
  wrong_guesses: 1,
}
const STANDINGS = [ME, RIVAL]

// Seeded in setup, before `RoomView` mounts: it sees an established membership
// and so never tries to join over a socket that isn't there.
function toLobby(): void {
  game.reset()
  room.setRoomState(devRoomState(ME))
}
toLobby()

const { fps, worst, janky, watch, reset: resetFrames } = useFrameRate()

function startRound(): void {
  game.reset()
  resetFrames()
  room.setRoomState(devRoomState(ME, { in_progress: true }))
  game.applyEvents(roundInPlay(ME))
}

/** Ends the round the way one really ends — deciding guess, outro, results. */
function finish(winners: Player[], win = false): void {
  if (!game.state.image) startRound()
  resetFrames()
  watch()
  game.applyEvents(roundWon(winners, STANDINGS, win))
}

function abort(): void {
  if (!game.state.image) startRound()
  game.applyEvents(roundAborted())
}

const status = computed(() => game.state.status)
const collapsed = ref(false)
</script>

<template>
  <RoomView code="DEV" />

  <!-- Fixed, so the harness never changes the layout it exists to test. Above
       the confetti canvas (z-40) so the buttons stay clickable under a volley.

       Opaque, not blurred: sitting above the canvas puts the confetti in this
       bar's backdrop, and a full-width backdrop-filter re-blurs on every frame
       the paper moves. That's the harness making itself look slow. -->
  <div
    class="fixed inset-x-0 bottom-0 z-50 flex flex-wrap items-center justify-center gap-2 border-t border-border bg-surface px-3 py-2"
  >
    <template v-if="!collapsed">
      <span class="mr-1 font-mono text-xs uppercase tracking-wider text-ink-faint">
        dev · {{ status }}
      </span>
      <!-- Fixed width: the digits change several times a second, and letting the
           readout resize shoves every button in this bar sideways as it does. -->
      <span v-if="worst" class="mr-1 w-56 shrink-0 font-mono text-xs text-ink-faint tabular-nums">
        {{ fps }}fps · worst {{ worst }}ms · {{ janky }} janky
      </span>
      <button
        class="rounded-lg border border-border bg-raised px-3 py-1.5 text-xs font-medium hover:border-turn hover:text-turn"
        @click="startRound"
      >
        Start round
      </button>
      <button
        class="rounded-lg bg-turn px-3 py-1.5 text-xs font-semibold text-on-accent"
        @click="finish([ME])"
      >
        Win now
      </button>
      <button
        class="rounded-lg border border-correct bg-correct/10 px-3 py-1.5 text-xs font-semibold text-correct"
        @click="finish([ME], true)"
      >
        Clean sweep
      </button>
      <button
        class="rounded-lg border border-border bg-raised px-3 py-1.5 text-xs font-medium hover:border-turn hover:text-turn"
        @click="finish([RIVAL])"
      >
        Rival wins
      </button>
      <!-- The sweep seen by someone who didn't win: fireworks, no cannons. -->
      <button
        class="rounded-lg border border-border bg-raised px-3 py-1.5 text-xs font-medium hover:border-correct hover:text-correct"
        @click="finish([RIVAL], true)"
      >
        Rival wins + sweep
      </button>
      <button
        class="rounded-lg border border-border bg-raised px-3 py-1.5 text-xs font-medium hover:border-wrong hover:text-wrong"
        @click="abort"
      >
        Abort
      </button>
      <button
        class="rounded-lg border border-border px-3 py-1.5 text-xs text-ink-muted hover:text-ink"
        @click="toLobby"
      >
        Lobby
      </button>
    </template>
    <button
      class="rounded-lg px-2 py-1.5 text-xs text-ink-faint hover:text-ink"
      :title="collapsed ? 'Show dev controls' : 'Hide dev controls'"
      @click="collapsed = !collapsed"
    >
      {{ collapsed ? '▲ dev' : '▼' }}
    </button>
  </div>
</template>
