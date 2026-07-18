<script setup lang="ts">
/**
 * Modal editor for room settings (search tags + NSFW). Seeds from the current
 * snapshot when opened; applying broadcasts via `configure_room`, so every
 * player's lobby summary updates. Closing without Apply discards the edits.
 */
import { ref } from 'vue'

import { useRoomStore } from '@/stores/room'

const room = useRoomStore()

const dialog = ref<HTMLDialogElement | null>(null)
const queryText = ref('')
const nsfw = ref(false)

function open(): void {
  queryText.value = (room.roomState?.query ?? []).join(', ')
  nsfw.value = room.roomState?.nsfw ?? false
  dialog.value?.showModal()
}

function close(): void {
  dialog.value?.close()
}

function apply(): void {
  room.configureRoom({ query: queryText.value, nsfw: nsfw.value })
  close()
}

// Native <dialog> doesn't dismiss on backdrop click; a click on the element
// itself (not its content) is the backdrop.
function onBackdrop(event: MouseEvent): void {
  if (event.target === dialog.value) close()
}

defineExpose({ open })
</script>

<template>
  <dialog
    ref="dialog"
    class="m-auto w-[min(28rem,90vw)] rounded-xl border border-border bg-surface p-0 text-ink shadow-2xl backdrop:bg-black/60"
    @click="onBackdrop"
  >
    <form class="flex flex-col gap-4 p-5" @submit.prevent="apply">
      <h2 class="font-display text-xl font-bold">Room settings</h2>

      <label class="flex flex-col gap-1 text-sm">
        <span class="text-ink-muted">Search tags (comma or newline separated)</span>
        <textarea
          v-model="queryText"
          rows="3"
          placeholder="e.g. safe, pony"
          class="resize-y rounded-lg border border-border bg-raised px-2 py-1 text-sm text-ink placeholder:text-ink-faint focus:border-turn focus:outline-none"
        />
      </label>

      <label class="flex items-center gap-2 text-sm">
        <input v-model="nsfw" type="checkbox" class="accent-turn" />
        Allow NSFW results
      </label>

      <div class="flex justify-end gap-2">
        <button
          type="button"
          class="rounded-lg border border-border px-3 py-1.5 text-sm font-medium hover:bg-raised"
          @click="close"
        >
          Cancel
        </button>
        <button type="submit" class="rounded-lg bg-turn px-4 py-1.5 text-sm font-semibold text-[#07101f]">
          Apply
        </button>
      </div>
    </form>
  </dialog>
</template>
