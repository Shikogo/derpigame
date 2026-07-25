/**
 * The social side-channel — a plain message list. Never the guess path: guesses
 * go through `room.submitGuess`, not here.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { log } from '@/lib/logger'
import { emitAck } from '@/socket/client'
import type { ChatMessage } from '@/types/wire'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])

  /**
   * How many messages have arrived unseen. Only the phone layout, which keeps
   * chat behind a closed sheet, has anywhere to show this — on desktop chat is
   * always on screen and the count just drifts, unread by anything.
   */
  const readCount = ref(0)
  const unread = computed(() => Math.max(0, messages.value.length - readCount.value))

  function receive(message: ChatMessage): void {
    messages.value.push(message)
  }

  function markRead(): void {
    readCount.value = messages.value.length
  }

  async function send(text: string): Promise<void> {
    const trimmed = text.trim()
    if (!trimmed) return
    try {
      await emitAck('chat', { text: trimmed })
    } catch (err) {
      // Best-effort side-channel: a silent server / dropped socket is a no-op,
      // not an unhandled rejection.
      log.debug('chat send failed:', err)
    }
  }

  function reset(): void {
    messages.value = []
    readCount.value = 0
  }

  return { messages, unread, receive, markRead, send, reset }
})
