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
const showGame = computed(() => !game.ended && (room.inProgress || game.state.status === 'active'))
// A live round with a picture — the point where the rail shows the turn controls.
const live = computed(() => game.state.status === 'active' && !!game.state.image)
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
        <button class="text-sm text-ink-faint underline hover:text-wrong" @click="leave">
          Leave
        </button>
      </header>

      <div class="grid flex-1 gap-4 lg:min-h-0 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div class="flex min-w-0 flex-col gap-4">
          <p v-if="notice" class="rounded-lg bg-wrong/10 px-3 py-2 text-sm text-wrong">
            {{ notice }}
          </p>
          <AgeGate v-if="needsAgeGate" @confirm="session.acknowledgeNsfw()" @decline="leave" />
          <GameOverPanel v-else-if="showGameOver" @back="backToLobby" />
          <GamePanel v-else-if="showGame" />
          <LobbyPanel v-else />
        </div>
        <aside class="flex min-w-0 flex-col gap-4 lg:min-h-0 lg:overflow-hidden">
          <GameControls v-if="live && !needsAgeGate" />
          <ChatPanel class="h-[22rem] shrink-0" />
        </aside>
      </div>
    </template>
  </main>
</template>
