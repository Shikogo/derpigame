import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useChatStore } from '@/stores/chat'

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('chat store — unread', () => {
  it('counts messages since the last read and clears on marking', () => {
    const chat = useChatStore()
    expect(chat.unread).toBe(0)

    chat.receive({ name: 'A', text: 'hi' })
    chat.receive({ name: 'B', text: 'yo' })
    expect(chat.unread).toBe(2)

    chat.markRead()
    expect(chat.unread).toBe(0)

    // Reading isn't permanent — later messages count again.
    chat.receive({ name: 'A', text: 'still here' })
    expect(chat.unread).toBe(1)
  })

  it('clears the read watermark along with the messages', () => {
    const chat = useChatStore()
    chat.receive({ name: 'A', text: 'hi' })
    chat.markRead()

    chat.reset()
    expect(chat.messages).toEqual([])

    // A stale watermark would swallow the new room's first messages.
    chat.receive({ name: 'B', text: 'new room' })
    expect(chat.unread).toBe(1)
  })
})
