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
    class="m-auto w-[min(28rem,90vw)] rounded-xl p-0 backdrop:bg-black/40"
    @click="onBackdrop"
  >
    <form class="flex flex-col gap-4 p-5" @submit.prevent="apply">
      <h2 class="text-lg font-semibold">Room settings</h2>

      <label class="flex flex-col gap-1 text-sm">
        <span class="text-gray-500">Search tags (comma or newline separated)</span>
        <textarea
          v-model="queryText"
          rows="3"
          placeholder="e.g. safe, pony"
          class="resize-y rounded border border-gray-300 px-2 py-1 text-sm focus:border-turn focus:outline-none"
        />
      </label>

      <label class="flex items-center gap-2 text-sm">
        <input v-model="nsfw" type="checkbox" class="accent-turn" />
        Allow NSFW results
      </label>

      <div class="flex justify-end gap-2">
        <button
          type="button"
          class="rounded border border-gray-300 px-3 py-1.5 text-sm font-medium hover:bg-gray-50"
          @click="close"
        >
          Cancel
        </button>
        <button type="submit" class="rounded bg-turn px-4 py-1.5 text-sm font-semibold text-white">
          Apply
        </button>
      </div>
    </form>
  </dialog>
</template>
