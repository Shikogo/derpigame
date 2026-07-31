import { beforeEach, describe, expect, it } from 'vitest'

import { forgetRoom, recallRoom, rememberRoom, roomRoute } from '@/lib/roomCode'

describe('roomCode', () => {
  beforeEach(() => sessionStorage.clear())

  it('remembers, recalls and forgets the room', () => {
    expect(recallRoom()).toBeNull()

    rememberRoom('brave-clever-kirin')
    expect(recallRoom()).toBe('brave-clever-kirin')

    forgetRoom()
    expect(recallRoom()).toBeNull()
  })

  it('keeps the code out of the route only while hidden', () => {
    expect(roomRoute('brave-clever-kirin', false)).toEqual({
      name: 'room',
      params: { code: 'brave-clever-kirin' },
    })
    expect(roomRoute('brave-clever-kirin', true)).toEqual({ name: 'room', params: { code: '' } })
  })
})
