/**
 * Wire the shared socket's inbound channels to the Pinia stores. Called once at
 * startup, after Pinia is installed — keeping the stores themselves free of
 * socket-registration side effects (so they stay unit-testable in isolation).
 */

import { socket } from '@/socket/client'
import { useChatStore } from '@/stores/chat'
import { useGameStore } from '@/stores/game'
import { useRoomStore } from '@/stores/room'

export function bindSocketToStores(): void {
  const room = useRoomStore()
  const game = useGameStore()
  const chat = useChatStore()

  socket.on('connect', () => room.setConnected(true))
  socket.on('disconnect', () => room.setConnected(false))
  socket.on('room_state', (state) => room.setRoomState(state))
  socket.on('game_events', (events) => game.applyEvents(events))
  socket.on('chat', (message) => chat.receive(message))
}
