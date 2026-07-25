<script setup lang="ts">
/** The social side-channel. Purely chat — guesses never travel through here. */
import { nextTick, ref, watch } from 'vue'

import { useChatStore } from '@/stores/chat'

const chat = useChatStore()
const text = ref('')
const listEl = ref<HTMLElement | null>(null)

async function send(): Promise<void> {
  const value = text.value.trim()
  if (!value) return
  text.value = ''
  await chat.send(value)
}

// Keep the newest message in view.
watch(
  () => chat.messages.length,
  async () => {
    await nextTick()
    listEl.value?.scrollTo({ top: listEl.value.scrollHeight })
  },
)
</script>

<template>
  <section class="flex min-h-0 flex-col rounded-lg border border-border bg-surface">
    <h3 class="border-b border-border px-3 py-2 text-sm font-semibold text-ink-muted">Chat</h3>
    <ul ref="listEl" class="flex-1 space-y-1 overflow-y-auto overscroll-contain p-3 text-sm">
      <li v-for="(m, i) in chat.messages" :key="i">
        <span class="font-semibold text-turn">{{ m.name }}:</span> {{ m.text }}
      </li>
      <li v-if="!chat.messages.length" class="text-ink-faint">No messages yet.</li>
    </ul>
    <form class="flex gap-2 border-t border-border p-2" @submit.prevent="send">
      <input
        v-model="text"
        type="text"
        placeholder="Say something…"
        class="flex-1 rounded border border-border bg-raised px-2 py-1 text-sm text-ink placeholder:text-ink-faint focus:border-turn focus:outline-none"
      />
      <button type="submit" class="rounded bg-turn px-3 py-1 text-sm font-medium text-on-accent">
        Send
      </button>
    </form>
  </section>
</template>
