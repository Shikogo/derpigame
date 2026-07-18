/**
 * Room lifecycle + lobby snapshot. Actions emit client→server events and map
 * their acks; `error` holds the last failure string (`room_not_found`,
 * `name_taken`, `no_players_ready`, `not_your_turn`, …) for the UI to render.
 * The inbound `room_state` broadcast lands here via `setRoomState`.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { emitAck } from '@/socket/client'
import { useChatStore } from '@/stores/chat'
import { useGameStore } from '@/stores/game'
import { useSessionStore } from '@/stores/session'
import type { Ack, QueryInput, RoomState } from '@/types/wire'

export const useRoomStore = defineStore('room', () => {
  const roomState = ref<RoomState | null>(null)
  const connected = ref(false)
  const error = ref<string | null>(null)

  const code = computed(() => roomState.value?.room ?? null)
  const inProgress = computed(() => roomState.value?.in_progress ?? false)
  const users = computed(() => roomState.value?.users ?? [])
  const me = computed(() => {
    const uuid = useSessionStore().uuid
    return users.value.find((u) => u.uuid === uuid) ?? null
  })

  /** Emit an ack-bearing event; record the error string, return the raw ack. */
  async function request(event: string, payload: Record<string, unknown> = {}): Promise<Ack> {
    try {
      const ack = await emitAck<Ack>(event, payload)
      error.value = ack.ok ? null : ack.error
      return ack
    } catch {
      error.value = 'timeout' // silent server / lost connection
      return { ok: false, error: 'timeout' }
    }
  }

  function absorbJoin(ack: Ack): void {
    if (ack.ok && ack.room_state) roomState.value = ack.room_state
  }

  async function createRoom(
    name: string,
    opts: { nsfw?: boolean; query?: QueryInput } = {},
  ): Promise<Ack> {
    const session = useSessionStore()
    session.setName(name)
    const ack = await request('create_room', { name, uuid: session.uuid, ...opts })
    absorbJoin(ack)
    return ack
  }

  async function joinRoom(roomCode: string, name: string): Promise<Ack> {
    const session = useSessionStore()
    session.setName(name)
    const ack = await request('join_room', {
      room: roomCode,
      name,
      uuid: session.uuid,
    })
    absorbJoin(ack)
    return ack
  }

  async function setReady(ready: boolean): Promise<Ack> {
    return request('set_ready', { ready })
  }

  async function configureRoom(config: { query?: QueryInput; nsfw?: boolean }): Promise<Ack> {
    return request('configure_room', config)
  }

  async function startGame(): Promise<Ack> {
    return request('start_game')
  }

  async function stopGame(): Promise<Ack> {
    return request('stop_game')
  }

  async function submitGuess(guess: string): Promise<Ack> {
    return request('submit_guess', { guess })
  }

  async function leaveRoom(): Promise<Ack> {
    const ack = await request('leave_room')
    roomState.value = null
    useGameStore().reset() // drop the last round's feed/scoreboard/image…
    useChatStore().reset() // …and messages, so the next room starts clean
    return ack
  }

  function setRoomState(state: RoomState): void {
    roomState.value = state
  }

  function setConnected(value: boolean): void {
    connected.value = value
  }

  return {
    roomState,
    connected,
    error,
    code,
    inProgress,
    users,
    me,
    createRoom,
    joinRoom,
    setReady,
    configureRoom,
    startGame,
    stopGame,
    submitGuess,
    leaveRoom,
    setRoomState,
    setConnected,
  }
})