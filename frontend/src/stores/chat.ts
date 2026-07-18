/**
 * The social side-channel — a plain message list. Never the guess path: guesses
 * go through `room.submitGuess`, not here.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

import { emitAck } from '@/socket/client'
import type { ChatMessage } from '@/types/wire'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])

  function receive(message: ChatMessage): void {
    messages.value.push(message)
  }

  async function send(text: string): Promise<void> {
    const trimmed = text.trim()
    if (!trimmed) return
    try {
      await emitAck('chat', { text: trimmed })
    } catch {
      // Best-effort side-channel: a silent server / dropped socket is a no-op,
      // not an unhandled rejection.
    }
  }

  function reset(): void {
    messages.value = []
  }

  return { messages, receive, send, reset }
})