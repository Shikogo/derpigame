<script setup lang="ts">
/**
 * The between-rounds lobby: roster, your ready toggle, room config (query +
 * nsfw), start, a copyable invite link, and the round history.
 */
import { computed, ref, watch } from 'vue'

import HistoryPanel from '@/components/HistoryPanel.vue'
import UserList from '@/components/UserList.vue'
import { errorLabel } from '@/lib/errors'
import { useRoomStore } from '@/stores/room'

const room = useRoomStore()

const queryText = ref('')
const nsfw = ref(false)

// Seed the config editor from the latest snapshot (and whenever it changes).
watch(
  () => room.roomState,
  (state) => {
    queryText.value = (state?.query ?? []).join(', ')
    nsfw.value = state?.nsfw ?? false
  },
  { immediate: true },
)

const ready = computed(() => room.me?.ready ?? false)
const anyReady = computed(() => room.users.some((u) => u.ready))

const inviteLink = computed(
  () => `${location.origin}${location.pathname}#/room/${room.code}`,
)
const copied = ref(false)
async function copyInvite(): Promise<void> {
  try {
    await navigator.clipboard.writeText(inviteLink.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    // Clipboard blocked (insecure context) — the field is selectable instead.
  }
}

function applyConfig(): void {
  room.configureRoom({ query: queryText.value, nsfw: nsfw.value })
}
</script>

<template>
  <div class="flex flex-col gap-5">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold">Lobby</h2>
      <button
        class="rounded-lg px-4 py-2 text-sm font-semibold"
        :class="ready ? 'bg-correct text-white' : 'border border-gray-300 hover:bg-gray-50'"
        @click="room.setReady(!ready)"
      >
        {{ ready ? 'Ready ✓' : 'Ready up' }}
      </button>
    </div>

    <UserList />

    <fieldset class="flex flex-col gap-3 rounded-lg border border-gray-200 p-3">
      <legend class="px-1 text-sm font-semibold text-gray-600">Room settings</legend>
      <label class="flex flex-col gap-1 text-sm">
        <span class="text-gray-500">Search tags (comma or newline separated)</span>
        <textarea
          v-model="queryText"
          rows="2"
          placeholder="e.g. safe, pony"
          class="resize-y rounded border border-gray-300 px-2 py-1 text-sm focus:border-turn focus:outline-none"
        />
      </label>
      <label class="flex items-center gap-2 text-sm">
        <input v-model="nsfw" type="checkbox" class="accent-turn" />
        Allow NSFW results
      </label>
      <button
        class="self-start rounded border border-gray-300 px-3 py-1.5 text-sm font-medium hover:bg-gray-50"
        @click="applyConfig"
      >
        Apply settings
      </button>
    </fieldset>

    <div class="flex flex-col gap-2">
      <button
        class="rounded-lg bg-turn px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
        :disabled="!anyReady"
        @click="room.startGame()"
      >
        Start game
      </button>
      <p v-if="!anyReady" class="text-xs text-gray-400">At least one player must ready up.</p>
      <p v-else-if="room.error" class="text-xs text-wrong">{{ errorLabel(room.error) }}</p>
    </div>

    <div class="flex flex-col gap-1">
      <span class="text-sm font-semibold text-gray-600">Invite link</span>
      <div class="flex gap-2">
        <input
          :value="inviteLink"
          readonly
          class="flex-1 truncate rounded border border-gray-300 px-2 py-1 text-xs text-gray-500"
          @focus="(e) => (e.target as HTMLInputElement).select()"
        />
        <button
          class="rounded border border-gray-300 px-3 py-1 text-xs font-medium hover:bg-gray-50"
          @click="copyInvite"
        >
          {{ copied ? 'Copied!' : 'Copy' }}
        </button>
      </div>
    </div>

    <HistoryPanel />
  </div>
</template>
