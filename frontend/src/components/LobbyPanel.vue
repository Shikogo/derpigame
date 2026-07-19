<script setup lang="ts">
/**
 * The between-rounds lobby: roster, your ready toggle, a read-only settings
 * summary (editing lives in a dialog), start, a copyable invite link, and the
 * round history.
 */
import { computed, ref } from 'vue'

import HistoryPanel from '@/components/HistoryPanel.vue'
import RoomSettingsDialog from '@/components/RoomSettingsDialog.vue'
import UserList from '@/components/UserList.vue'
import { errorLabel } from '@/lib/errors'
import { useRoomStore } from '@/stores/room'

const room = useRoomStore()

const settingsDialog = ref<{ open: () => void } | null>(null)

const querySummary = computed(() => {
  const query = room.roomState?.query ?? []
  return query.length ? query.join(', ') : 'anything'
})
const nsfwOn = computed(() => room.roomState?.nsfw ?? false)
const turnSeconds = computed(() => room.roomState?.turn_seconds ?? 30)

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
</script>

<template>
  <div class="flex flex-col gap-5">
    <div class="flex items-center justify-between">
      <h2 class="font-display text-xl font-bold">Lobby</h2>
      <button
        class="rounded-lg px-4 py-2 text-sm font-semibold"
        :class="ready ? 'bg-correct text-on-accent' : 'border border-border hover:bg-raised'"
        @click="room.setReady(!ready)"
      >
        {{ ready ? 'Ready ✓' : 'Ready up' }}
      </button>
    </div>

    <UserList />

    <div class="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface p-3">
      <div class="flex min-w-0 flex-col gap-0.5 text-sm">
        <span class="truncate">
          <span class="text-ink-muted">Searching:</span>
          <span class="font-medium">{{ querySummary }}</span>
        </span>
        <span class="text-xs text-ink-faint">
          NSFW: {{ nsfwOn ? 'on' : 'off' }} · {{ turnSeconds }}s per turn
        </span>
      </div>
      <button
        class="shrink-0 rounded border border-border px-3 py-1.5 text-sm font-medium hover:bg-raised"
        @click="settingsDialog?.open()"
      >
        ⚙ Edit
      </button>
    </div>
    <RoomSettingsDialog ref="settingsDialog" />

    <div class="flex flex-col gap-2">
      <button
        class="rounded-lg bg-turn px-4 py-2.5 text-sm font-semibold text-on-accent disabled:opacity-40"
        :disabled="!anyReady"
        @click="room.startGame()"
      >
        Start game
      </button>
      <p v-if="!anyReady" class="text-xs text-ink-faint">At least one player must ready up.</p>
      <p v-else-if="room.error" class="text-xs text-wrong">{{ errorLabel(room.error) }}</p>
    </div>

    <div class="flex flex-col gap-1">
      <span class="text-sm font-semibold text-ink-muted">Invite link</span>
      <div class="flex gap-2">
        <input
          :value="inviteLink"
          readonly
          class="flex-1 truncate rounded border border-border bg-raised px-2 py-1 font-mono text-xs text-ink-muted"
          @focus="(e) => (e.target as HTMLInputElement).select()"
        />
        <button
          class="rounded border border-border px-3 py-1 text-xs font-medium hover:bg-raised"
          @click="copyInvite"
        >
          {{ copied ? 'Copied!' : 'Copy' }}
        </button>
      </div>
    </div>

    <HistoryPanel />
  </div>
</template>
