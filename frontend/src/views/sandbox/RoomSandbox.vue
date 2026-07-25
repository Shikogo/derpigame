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
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'

import RoomView from '@/views/RoomView.vue'
import {
  RIVAL,
  devRoomState,
  rivalGuesses,
  roundAborted,
  roundInPlay,
  roundWon,
} from '@/views/sandbox/fixtures'
import { useFrameRate } from '@/views/sandbox/useFrameRate'
import { useKeyboardInset } from '@/composables/useKeyboardInset'
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

function rivalPlays(): void {
  if (!game.state.image) startRound()
  game.applyEvents(rivalGuesses())
}

/** Drop yourself from the round's roster — the dock's spectator branch. */
function toggleSpectating(): void {
  if (!game.state.image) startRound()
  const players = { ...game.state.players }
  if (players[ME.uuid]) delete players[ME.uuid]
  else players[ME.uuid] = ME
  game.state.players = players
}

/**
 * A stand-in keyboard: shrink the visual viewport the way Safari does and fire
 * the event it fires. A desktop window merely narrowed never does that, so
 * without this the whole iOS path — the measurement, the shell shrinking, the
 * sheet riding up, the viewer re-fitting — is unreachable outside a real phone.
 *
 * Overriding the height rather than writing `--kbd-inset` directly, so what runs
 * is the real measurement and not a stub of it.
 */
const FAKE_KEYBOARD_PX = 320
const fakeKeyboard = ref(false)

function toggleKeyboard(): void {
  const viewport = window.visualViewport
  if (!viewport) return
  fakeKeyboard.value = !fakeKeyboard.value
  if (fakeKeyboard.value) {
    Object.defineProperty(viewport, 'height', {
      configurable: true,
      get: () => window.innerHeight - FAKE_KEYBOARD_PX,
    })
  } else {
    // Deleting the own property hands `height` back to the prototype's getter.
    delete (viewport as unknown as Record<string, unknown>).height
  }
  viewport.dispatchEvent(new Event('resize'))
}

onBeforeUnmount(() => {
  if (fakeKeyboard.value) toggleKeyboard()
})

// What the layout is actually running on — the one readout worth having when
// the phone in your hand disagrees with the emulator.
const { inset } = useKeyboardInset()
const viewport = ref('')
function measure(): void {
  const vv = window.visualViewport
  viewport.value = `${window.innerWidth}×${window.innerHeight} · vv ${Math.round(vv?.height ?? 0)}`
}
onMounted(() => {
  measure()
  window.addEventListener('resize', measure)
  window.visualViewport?.addEventListener('resize', measure)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', measure)
  window.visualViewport?.removeEventListener('resize', measure)
})

const status = computed(() => game.state.status)
// The bar sits where the mobile dock does, so it starts out of the way there.
const collapsed = ref(window.innerWidth < 1024)
</script>

<template>
  <RoomView code="DEV" />

  <!-- Fixed, so the harness never changes the layout it exists to test. Above
       the confetti canvas (z-40) so the buttons stay clickable under a volley.

       Opaque, not blurred: sitting above the canvas puts the confetti in this
       bar's backdrop, and a full-width backdrop-filter re-blurs on every frame
       the paper moves. That's the harness making itself look slow.

       Below `lg` the bottom edge belongs to the guess dock, so the bar moves to
       the corner rather than sitting on the thing it exists to test. -->
  <div
    class="fixed z-50 flex flex-wrap items-center justify-center gap-2 border-border bg-surface px-3 py-2 max-lg:right-2 max-lg:top-2 max-lg:max-w-[14rem] max-lg:flex-col max-lg:items-stretch max-lg:rounded-lg max-lg:border lg:inset-x-0 lg:bottom-0 lg:border-t"
  >
    <template v-if="!collapsed">
      <span class="mr-1 font-mono text-xs uppercase tracking-wider text-ink-faint">
        dev · {{ status }}
      </span>
      <span class="mr-1 font-mono text-xs text-ink-faint tabular-nums">
        {{ viewport }} · kbd {{ inset }}
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
      <button
        class="rounded-lg border border-border bg-raised px-3 py-1.5 text-xs font-medium hover:border-turn hover:text-turn"
        @click="rivalPlays"
      >
        Rival guesses
      </button>
      <button
        class="rounded-lg border border-border bg-raised px-3 py-1.5 text-xs font-medium hover:border-turn hover:text-turn"
        @click="toggleSpectating"
      >
        Spectate
      </button>
      <button
        class="rounded-lg border px-3 py-1.5 text-xs font-medium"
        :class="
          fakeKeyboard
            ? 'border-turn bg-turn/10 text-turn'
            : 'border-border bg-raised hover:border-turn hover:text-turn'
        "
        @click="toggleKeyboard"
      >
        ⌨ keyboard
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
