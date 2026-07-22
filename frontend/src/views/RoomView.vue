<script setup lang="ts">
/**
 * A room: a name gate for deep links / refreshes, then the lobby, the live game,
 * or the game-over screen depending on state. Chat rides alongside throughout.
 *
 * Panel priority: a finished/aborted round shows the game-over screen even while
 * `in_progress` is briefly stale; otherwise `in_progress` (or a live game batch)
 * shows the game, and everything else is the lobby.
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AgeGate from '@/components/AgeGate.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import GameControls from '@/components/GameControls.vue'
import GameOverPanel from '@/components/GameOverPanel.vue'
import GamePanel from '@/components/GamePanel.vue'
import IconLeave from '@/components/icons/IconLeave.vue'
import LobbyPanel from '@/components/LobbyPanel.vue'
import { errorLabel } from '@/lib/errors'
import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'
import { useSessionStore } from '@/stores/session'

const props = defineProps<{ code: string }>()

const router = useRouter()
const room = useRoomStore()
const game = useGameStore()
const session = useSessionStore()

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

async function leave(): Promise<void> {
  await room.leaveRoom()
  router.push({ name: 'home' })
}

async function backToLobby(): Promise<void> {
  await room.setReady(false) // force a fresh room_state so in_progress clears
  game.reset()
}
</script>

<template>
  <main class="mx-auto flex min-h-full max-w-6xl flex-col p-4">
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
      <header class="mb-4 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <RouterLink to="/" class="font-display text-lg font-bold tracking-tight text-turn">
            derpigame
          </RouterLink>
          <span class="pill border border-border bg-raised font-mono uppercase text-ink">
            {{ code }}
          </span>
          <span class="flex items-center gap-1 text-xs text-ink-faint">
            <span
              class="h-2 w-2 rounded-full"
              :class="room.connected ? 'bg-correct' : 'bg-eliminated'"
            />
            {{ room.connected ? 'connected' : 'offline' }}
          </span>
        </div>
        <button
          class="grid h-8 w-8 place-items-center rounded-lg text-ink-faint transition-colors hover:bg-raised hover:text-wrong"
          title="Leave"
          aria-label="Leave"
          @click="leave"
        >
          <IconLeave class="h-[1.15rem] w-[1.15rem]" />
        </button>
      </header>

      <div class="grid flex-1 gap-4 lg:min-h-0 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div class="flex min-w-0 flex-col gap-4">
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
          <div class="grid min-w-0 flex-1">
            <Transition name="panel">
              <AgeGate v-if="needsAgeGate" @confirm="session.acknowledgeNsfw()" @decline="leave" />
              <GameOverPanel v-else-if="showGameOver" @back="backToLobby" />
              <GamePanel v-else-if="showGame" />
              <LobbyPanel v-else />
            </Transition>
          </div>
        </div>
        <aside class="flex min-w-0 flex-col gap-4 lg:min-h-0 lg:overflow-hidden">
          <GameControls v-if="live && !needsAgeGate" />
          <ChatPanel class="h-[22rem] shrink-0" />
        </aside>
      </div>
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
