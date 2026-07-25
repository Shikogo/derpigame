<script setup lang="ts">
/**
 * The between-rounds lobby: roster, the ready/start bar, a read-only settings
 * summary (editing lives in a dialog), a copyable invite link, and the round
 * history. The bar sits right under the roster — the two halves of starting a
 * round belong together, and everything below is setup you touch far less often.
 */
import { computed, ref } from 'vue'

import HistoryPanel from '@/components/HistoryPanel.vue'
import ReadyBar from '@/components/ReadyBar.vue'
import RoomSettingsDialog from '@/components/RoomSettingsDialog.vue'
import UserList from '@/components/UserList.vue'
import { useRoomStore } from '@/stores/room'

const room = useRoomStore()

const settingsDialog = ref<{ open: () => void } | null>(null)

const querySummary = computed(() => {
  const query = room.roomState?.query ?? []
  return query.length ? query.join(', ') : 'anything'
})
const nsfwOn = computed(() => room.roomState?.nsfw ?? false)
const turnSeconds = computed(() => room.roomState?.turn_seconds ?? 30)

/** Every search bound and rating cap, `·`-separated. `null` means no limit. */
const boundsSummary = computed(() => {
  const state = room.roomState
  if (!state) return []
  const parts = [
    state.min_tag_count === null ? 'any tag count' : `${state.min_tag_count}+ tags`,
    state.min_score === null ? 'any score' : `score ${state.min_score}+`,
  ]
  for (const axis of state.rating_axes) {
    const cap = state.rating_caps[axis.key]
    parts.push(`${axis.label.toLowerCase()} ${cap ? `≤ ${cap}` : 'any'}`)
  }
  return parts
})

const inviteLink = computed(() => `${location.origin}${location.pathname}#/room/${room.code}`)
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

    <div
      class="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface p-3"
    >
      <div class="flex min-w-0 flex-col gap-0.5 text-sm">
        <span class="truncate">
          <span class="text-ink-muted">Searching: </span>
          <span class="font-medium">{{ querySummary }}</span>
        </span>
        <span class="text-xs text-ink-faint">
          NSFW: {{ nsfwOn ? 'on' : 'off' }} · {{ turnSeconds }}s per turn
        </span>
        <span class="text-xs text-ink-faint">{{ boundsSummary.join(' · ') }}</span>
      </div>
      <button
        class="shrink-0 rounded border border-border px-3 py-1.5 text-sm font-medium hover:bg-raised"
        @click="settingsDialog?.open()"
      >
        ⚙ Edit
      </button>
    </div>
    <RoomSettingsDialog ref="settingsDialog" />

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
