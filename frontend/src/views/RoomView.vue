<script setup lang="ts">
/**
 * A room: a name gate for deep links / refreshes, then the lobby, the live game,
 * or the game-over screen depending on state.
 *
 * Panel priority: a finished/aborted round shows the game-over screen even while
 * `in_progress` is briefly stale; otherwise `in_progress` (or a live game batch)
 * shows the game, and everything else is the lobby.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import AgeGate from '@/components/AgeGate.vue'
import BottomSheet from '@/components/BottomSheet.vue'
import GameOverPanel from '@/components/GameOverPanel.vue'
import GamePanel from '@/components/GamePanel.vue'
import GuessDock from '@/components/GuessDock.vue'
import IconLeave from '@/components/icons/IconLeave.vue'
import LobbyPanel from '@/components/LobbyPanel.vue'
import RoundLog from '@/components/RoundLog.vue'
import RoundStatusStrip from '@/components/RoundStatusStrip.vue'
import { useKeyboardInset } from '@/composables/useKeyboardInset'
import { errorLabel } from '@/lib/errors'
import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'
import { useSessionStore } from '@/stores/session'

const props = defineProps<{ code: string }>()

const router = useRouter()
const room = useRoomStore()
const game = useGameStore()
const session = useSessionStore()
const { open: keyboardOpen } = useKeyboardInset()

const isMember = computed(
  () => room.code?.toLowerCase() === props.code.toLowerCase() && room.me !== null,
)

const joinName = ref(session.name)
const joining = ref(false)
const reconnecting = ref(false)

async function join(): Promise<void> {
  const value = joinName.value.trim()
  if (!value || joining.value) return
  joining.value = true
  await room.joinRoom(props.code, value)
  joining.value = false
}

onMounted(async () => {
  // Deep link / refresh into a room we're not in: auto-join if we already have a
  // name (a reload reclaims the room within the backend's grace window),
  // otherwise the gate below asks for one.
  if (!isMember.value && session.name) {
    reconnecting.value = true
    await join()
    reconnecting.value = false
  }
})

const showGameOver = computed(() => game.ended)
const showGame = computed(
  () =>
    !game.ended &&
    (room.inProgress || game.state.status === 'active' || game.state.status === 'ending'),
)
// A live round with a picture — the point where the rail shows the turn controls.
// Held through `ending` too, so the rail doesn't collapse during the outro.
const live = computed(
  () => (game.state.status === 'active' || game.state.status === 'ending') && !!game.state.image,
)
// Block the picture (live round or the game-over reveal) behind a 18+ gate when
// the room shows NSFW and this viewer hasn't attested yet.
const needsAgeGate = computed(
  () => room.nsfw && !session.nsfwAck && (showGame.value || showGameOver.value),
)
const notice = computed(() => {
  if (showGame.value) return null
  if (game.state.status === 'no_image')
    return `No image found for “${(game.state.noImageQuery ?? []).join(', ')}”. Try a different query.`
  if (game.state.status === 'image_error')
    return 'The image source is unavailable right now. Try again in a moment.'
  return null
})

/**
 * A round on screen, past the age gate. Everything in the rail — the status
 * strip, the guess box, the log — belongs to a round, so this is also whether
 * there's a rail at all: the lobby and the results screen run one column.
 */
const roundLive = computed(() => live.value && !needsAgeGate.value)

/**
 * The same state, named for what it does below `lg`: a live round runs as a
 * fixed-height shell instead of a scrolling page, where the picture takes what's
 * left after a compact header, the status strip and the docked guess box, so both
 * the picture and the box stay on screen while you type. The lobby, the age gate
 * and the results screen keep scrolling — there's nothing they need to hold in
 * view.
 *
 * Everything the shell needs is a `max-lg:` class, so the desktop layout is the
 * one that was always here.
 */
const mobileShell = roundLive

// The guess feed and the standings, tucked behind the guess box on a phone — the
// overlay cards carry the verdicts, so a round is playable without ever opening
// this.
const sheetOpen = ref(false)

// Your turn arriving already focuses the guess box; clearing the sheet off the
// picture is the same thought.
watch(
  () => game.isMyTurn,
  (mine) => {
    if (mine) sheetOpen.value = false
  },
)
// The sheet is `position: fixed` — left open it would cover the results.
watch(mobileShell, (on) => {
  if (!on) sheetOpen.value = false
})
// Safari scrolls the layout viewport up on focus even with nothing to scroll.
watch(keyboardOpen, (on) => {
  if (on && mobileShell.value) window.scrollTo(0, 0)
})

// Leaving drops your seat and can't be taken back, and the button sits close
// enough to the results screen's own way out that players were hitting it by
// mistake — so it asks first. Declining the age gate still leaves outright:
// that answer is already deliberate.
const leaveDialog = ref<HTMLDialogElement | null>(null)

function askLeave(): void {
  leaveDialog.value?.showModal()
}

async function leave(): Promise<void> {
  leaveDialog.value?.close()
  await room.leaveRoom()
  router.push({ name: 'home' })
}

// Native <dialog> doesn't dismiss on backdrop click; a click on the element
// itself (not its content) is the backdrop.
function onLeaveBackdrop(event: MouseEvent): void {
  if (event.target === leaveDialog.value) leaveDialog.value?.close()
}

async function backToLobby(): Promise<void> {
  await room.returnToLobby()
  game.reset()
}
</script>

<template>
  <!-- Taken out of flow rather than merely height-capped: with no content in the
       document there is nothing for the page to scroll, so `min-h-full` can't
       fight the calc and a stray drag can't reveal anything underneath.
       `inset-x-0` is `mx-auto max-w-6xl` below `lg`, where the viewport is
       narrower than 72rem anyway. -->
  <main
    class="mx-auto flex min-h-full max-w-6xl flex-col p-4"
    :class="
      mobileShell &&
      'max-lg:fixed max-lg:inset-x-0 max-lg:top-0 max-lg:h-[calc(100dvh-var(--kbd-inset,0px))] max-lg:min-h-0 max-lg:overflow-hidden max-lg:p-0'
    "
    :data-mobile-shell="mobileShell || undefined"
  >
    <!-- reconnecting / name gate -->
    <div v-if="!isMember" class="m-auto w-full max-w-sm">
      <div
        v-if="reconnecting && !room.error"
        class="rounded-xl border border-border bg-surface p-6 text-center text-sm text-ink-muted"
      >
        Reconnecting to room <span class="font-mono uppercase text-turn">{{ code }}</span
        >…
      </div>
      <div v-else class="rounded-xl border border-border bg-surface p-6">
        <h1 class="mb-1 font-display text-xl font-bold">
          Join room <span class="font-mono uppercase text-turn">{{ code }}</span>
        </h1>
        <p class="mb-4 text-sm text-ink-muted">Pick a name to join.</p>
        <form class="flex flex-col gap-3" @submit.prevent="join">
          <input
            v-model="joinName"
            placeholder="Your name"
            class="rounded-lg border border-border bg-raised px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-turn focus:outline-none"
          />
          <button
            :disabled="!joinName.trim() || joining"
            class="rounded-lg bg-turn px-4 py-2 text-sm font-semibold text-on-accent disabled:opacity-40"
          >
            Join
          </button>
        </form>
        <p v-if="room.error" class="mt-2 text-sm text-wrong">{{ errorLabel(room.error) }}</p>
        <RouterLink to="/" class="mt-3 inline-block text-xs text-ink-faint underline">
          Back home
        </RouterLink>
      </div>
    </div>

    <!-- in the room -->
    <template v-else>
      <!-- Everything here has to survive a 360px-wide phone without pushing the
           leave button off the end, so the row shrinks in order of how much each
           part earns its width. -->
      <header
        class="mb-4 flex items-center justify-between gap-2 sm:gap-3"
        :class="
          mobileShell &&
          'max-lg:mb-0 max-lg:shrink-0 max-lg:border-b max-lg:border-border max-lg:px-3 max-lg:py-2'
        "
      >
        <div class="flex min-w-0 items-center gap-2 sm:gap-3">
          <RouterLink
            to="/"
            class="shrink-0 font-display text-base font-bold tracking-tight text-turn sm:text-lg"
          >
            derpigame
          </RouterLink>
          <span class="pill min-w-0 border border-border bg-raised font-mono uppercase text-ink">
            <span class="truncate">{{ code }}</span>
          </span>
          <!-- The word is the first thing to go: the dot already says it, and it
               keeps its meaning through the tooltip and the label. -->
          <span
            class="flex shrink-0 items-center gap-1 text-xs text-ink-faint"
            :title="room.connected ? 'Connected' : 'Offline'"
          >
            <span
              class="h-2 w-2 rounded-full"
              :class="room.connected ? 'bg-correct' : 'bg-eliminated'"
            />
            <span class="sr-only sm:not-sr-only">
              {{ room.connected ? 'connected' : 'offline' }}
            </span>
          </span>
        </div>
        <button
          class="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-ink-faint transition-colors hover:bg-raised hover:text-wrong"
          title="Leave"
          aria-label="Leave"
          @click="askLeave"
        >
          <IconLeave class="h-[1.15rem] w-[1.15rem]" />
        </button>
      </header>

      <!-- The `min-h-0` runs all the way down to the panel cell: it's what lets
           the picture give up height to the keyboard instead of shoving the
           guess box out through the bottom of the shell. -->
      <!-- The rail's column exists only while a round does; the lobby and the
           results screen have nothing to put beside them. -->
      <div
        class="grid flex-1 gap-4 lg:min-h-0"
        :class="
          roundLive &&
          'max-lg:min-h-0 max-lg:grid-rows-[minmax(0,1fr)_auto] max-lg:gap-0 lg:grid-cols-[minmax(0,1fr)_22rem]'
        "
      >
        <div class="flex min-w-0 flex-col gap-4" :class="mobileShell && 'max-lg:min-h-0'">
          <p v-if="notice" class="rounded-lg bg-wrong/10 px-3 py-2 text-sm text-wrong">
            {{ notice }}
          </p>
          <!-- Cross-faded rather than swapped: a decided round holds the picture
               through `ending` to play its last cards, and a hard cut straight
               to the results undoes that beat.

               Deliberately not `mode="out-in"`, which gates the incoming panel
               on the outgoing one's transition finishing — if that never
               resolves, nothing is left on screen at all. Overlapping them in a
               single grid cell makes an empty panel area impossible, and reads
               as a truer cross-fade besides. -->
          <!-- The panel's height lives here rather than on GamePanel, so the
               floor for a stacked layout and the shell's shrink-to-fit can't
               fight each other. It also catches the round ending: the shell
               releases while the panel is still fading out, and the floor keeps
               the leaving panel from collapsing mid-fade. -->
          <div
            class="grid min-w-0 flex-1"
            :class="mobileShell ? 'max-lg:min-h-0' : 'max-lg:min-h-[45svh]'"
          >
            <Transition name="panel">
              <AgeGate v-if="needsAgeGate" @confirm="session.acknowledgeNsfw()" @decline="leave" />
              <GameOverPanel v-else-if="showGameOver" @back="backToLobby" />
              <GamePanel v-else-if="showGame" />
              <LobbyPanel v-else />
            </Transition>
          </div>
        </div>
        <!-- One stack on desktop, three zones on a phone: the strip and the dock
             pin to the bottom of the shell and the rest becomes the sheet.
             Ordered so both readings fall out of the same markup — nothing is
             mounted twice, so crossing `lg` never restarts the turn timer. -->
        <aside
          v-if="roundLive"
          class="flex min-w-0 flex-col gap-4 max-lg:min-h-0 max-lg:gap-0 lg:min-h-0 lg:overflow-hidden"
        >
          <RoundStatusStrip :compact="keyboardOpen" />
          <GuessDock :sheet-open="sheetOpen" @toggle="sheetOpen = !sheetOpen" />
          <BottomSheet v-model:open="sheetOpen">
            <RoundLog />
          </BottomSheet>
        </aside>
      </div>

      <dialog
        ref="leaveDialog"
        class="m-auto w-[min(24rem,90vw)] rounded-xl border border-border bg-surface p-0 text-ink shadow-2xl backdrop:bg-black/60"
        @click="onLeaveBackdrop"
      >
        <div class="flex flex-col gap-4 p-5">
          <h2 class="font-display text-xl font-bold">Leave this room?</h2>
          <p class="text-sm text-ink-muted">
            You'll drop out of the room and go back to the home screen.
          </p>
          <div class="flex justify-end gap-2">
            <button
              type="button"
              class="rounded-lg border border-border px-3 py-1.5 text-sm font-medium hover:bg-raised"
              @click="leaveDialog?.close()"
            >
              Cancel
            </button>
            <button
              type="button"
              class="rounded-lg bg-wrong px-4 py-1.5 text-sm font-semibold text-on-accent"
              @click="leave()"
            >
              Leave
            </button>
          </div>
        </div>
      </dialog>
    </template>
  </main>
</template>

<style scoped>
/* Both panels share the one grid cell, so the incoming one never waits on the
   outgoing one and the area is never empty. */
.panel-enter-active,
.panel-leave-active {
  grid-column: 1;
  grid-row: 1;
}
.panel-enter-active {
  transition:
    opacity 0.28s ease-out,
    transform 0.28s ease-out;
}
.panel-leave-active {
  transition:
    opacity 0.18s ease-in,
    transform 0.18s ease-in;
}
.panel-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.panel-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
