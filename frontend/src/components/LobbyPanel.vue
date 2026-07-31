<script setup lang="ts">
/**
 * The between-rounds lobby: roster, the ready/start bar, the room settings, a
 * copyable invite link, and the round history. The bar sits right under the
 * roster — the two halves of starting a round belong together — and the settings
 * follow it, since changing them is most of what brings anyone back here.
 */
import { computed, ref } from 'vue'

import HistoryPanel from '@/components/HistoryPanel.vue'
import ReadyBar from '@/components/ReadyBar.vue'
import RoomSettings from '@/components/RoomSettings.vue'
import UserList from '@/components/UserList.vue'
import { MASKED_CODE } from '@/lib/roomCode'
import { usePreferencesStore } from '@/stores/preferences'
import { useRoomStore } from '@/stores/room'

const room = useRoomStore()
const prefs = usePreferencesStore()

// Built from the room snapshot, not the route, so the link stays real to hand
// out even when streamer mode has stripped the code from our own URL.
const inviteLink = computed(() => `${location.origin}${location.pathname}#/room/${room.code}`)
// Only the display is masked — Copy still puts the real link on the clipboard,
// which is what makes the mode usable rather than just blind.
const shownLink = computed(() =>
  prefs.streamerMode
    ? `${location.origin}${location.pathname}#/room/${MASKED_CODE}`
    : inviteLink.value,
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
  <!-- Capped and centred like the results screen: with no rail beside it the
       lobby would otherwise stretch the full width of the page. -->
  <div class="mx-auto flex w-full max-w-3xl flex-col gap-5">
    <h2 class="font-display text-xl font-bold">Lobby</h2>

    <UserList />

    <ReadyBar />

    <RoomSettings />

    <div class="flex flex-col gap-1">
      <span class="text-sm font-semibold text-ink-muted">Invite link</span>
      <div class="flex gap-2">
        <input
          :value="shownLink"
          readonly
          class="flex-1 truncate rounded border border-border bg-raised px-2 py-1 font-mono text-xs text-ink-muted"
          @focus="(e) => !prefs.streamerMode && (e.target as HTMLInputElement).select()"
        />
        <button
          class="rounded border border-border px-3 py-1 text-xs font-medium hover:bg-raised"
          @click="copyInvite"
        >
          {{ copied ? 'Copied!' : 'Copy' }}
        </button>
      </div>
      <!-- Without this the masked field just looks broken. -->
      <span v-if="prefs.streamerMode" class="text-xs text-ink-faint">
        Hidden for streaming — Copy still copies the real link.
      </span>
    </div>

    <HistoryPanel />
  </div>
</template>
