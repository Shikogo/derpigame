/**
 * The one Socket.IO connection to the backend.
 *
 * A thin wrapper: it holds the singleton socket, exposes an ack-aware `emitAck`
 * for the request/reply half of the contract, and types the three inbound
 * channels (`game_events`, `room_state`, `chat`). All game/lobby logic lives in
 * the stores — this module just moves bytes.
 */

import { io, type Socket } from 'socket.io-client'

import type { Ack, ChatMessage, GameEvent, RoomState } from '@/types/wire'

interface ServerToClientEvents {
  /** Batched, ordered list of typed game-event payloads. */
  game_events: (events: GameEvent[]) => void
  /** Whole-snapshot lobby state, rebroadcast on any membership/config change. */
  room_state: (state: RoomState) => void
  chat: (message: ChatMessage) => void
}

// Every client→server event takes a payload plus an ack callback; the names are
// open (create_room, join_room, submit_guess, …) so `emitAck` stays generic.
type ClientToServerEvents = Record<
  string,
  (payload: object, ack: (response: Ack) => void) => void
>

const ACK_TIMEOUT_MS = 8000

export const socket: Socket<ServerToClientEvents, ClientToServerEvents> = io(
  import.meta.env.VITE_BACKEND_URL,
  { autoConnect: false },
)

/**
 * Emit a client→server event and await its per-caller ack, rejecting if the
 * server stays silent past the timeout. Every contract event carries an ack.
 */
export async function emitAck<T = Ack>(event: string, payload: object = {}): Promise<T> {
  return (await socket.timeout(ACK_TIMEOUT_MS).emitWithAck(event, payload)) as T
}

export function connect(): void {
  if (!socket.connected) socket.connect()
}

export function disconnect(): void {
  socket.disconnect()
}
