/**
 * Wire the shared socket's inbound channels to the Pinia stores. Called once at
 * startup, after Pinia is installed — keeping the stores themselves free of
 * socket-registration side effects (so they stay unit-testable in isolation).
 */

import { log } from '@/lib/logger'
import { socket } from '@/socket/client'
import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'

export function bindSocketToStores(): void {
  const room = useRoomStore()
  const game = useGameStore()

  socket.on('connect', () => {
    log.info('socket connected')
    const reconnected = room.code !== null
    room.setConnected(true)
    if (reconnected) void room.rejoin()
  })
  socket.on('disconnect', (reason) => {
    log.warn('socket disconnected:', reason)
    room.setConnected(false)
  })
  socket.on('connect_error', (err) => log.warn('socket connect failed:', err.message))
  socket.on('room_state', (state) => room.setRoomState(state))
  socket.on('game_events', (events) => game.applyEvents(events))

  // A tab close or refresh unloads the page. Signal it while the socket is still
  // up so the server clears our seat on the short window — a refresh reconnects
  // within it, a real close does not — instead of the long network-drop grace.
  window.addEventListener('pagehide', () => {
    if (room.code) socket.emit('leaving')
  })
}
