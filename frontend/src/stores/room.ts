/**
 * Room lifecycle + lobby snapshot. Actions emit client→server events and map
 * their acks; `error` holds the last failure string (`room_not_found`,
 * `name_taken`, `not_ready`, `not_your_turn`, …) for the UI to render.
 * The inbound `room_state` broadcast lands here via `setRoomState`.
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { withWins } from '@/game/history'
import { log } from '@/lib/logger'
import { emitAck } from '@/socket/client'
import { useChatStore } from '@/stores/chat'
import { useGameStore } from '@/stores/game'
import { useSessionStore } from '@/stores/session'
import type { Ack, ConfigureRoomPayload, QueryInput, RoomState } from '@/types/wire'

export const useRoomStore = defineStore('room', () => {
  const roomState = ref<RoomState | null>(null)
  const connected = ref(false)
  const error = ref<string | null>(null)
  // The start ack only lands once the image is fetched and its tags resolved,
  // so the wait is long enough to need a spinner.
  const starting = ref(false)
  // Likewise a guess: resolving aliases can round-trip to Derpibooru first.
  const guessing = ref(false)

  const code = computed(() => roomState.value?.room ?? null)
  const inProgress = computed(() => roomState.value?.in_progress ?? false)
  const nsfw = computed(() => roomState.value?.nsfw ?? false)
  const source = computed(() => roomState.value?.source ?? 'derpibooru')
  const sources = computed(() => roomState.value?.sources ?? [])
  const users = computed(() => roomState.value?.users ?? [])
  const history = computed(() => roomState.value?.history ?? [])
  const winCounts = computed(() => roomState.value?.win_counts ?? [])
  const usersWithWins = computed(() => withWins(users.value, winCounts.value))
  // Room members not in the round's roster are spectators (only during a game).
  const spectators = computed(() => {
    if (!inProgress.value) return []
    const playing = useGameStore().roundPlayerUuids
    return users.value.filter((u) => !playing.has(u.uuid))
  })
  const spectatorCount = computed(() => spectators.value.length)
  const me = computed(() => {
    const uuid = useSessionStore().uuid
    return users.value.find((u) => u.uuid === uuid) ?? null
  })

  /** Emit an ack-bearing event; record the error string, return the raw ack. */
  async function request(event: string, payload: object = {}): Promise<Ack> {
    try {
      const ack = await emitAck<Ack>(event, payload)
      error.value = ack.ok ? null : ack.error
      return ack
    } catch (err) {
      log.warn(`emit '${event}' failed:`, err)
      error.value = 'timeout' // silent server / lost connection
      return { ok: false, error: 'timeout' }
    }
  }

  function absorbJoin(ack: Ack): void {
    if (ack.ok && ack.room_state) roomState.value = ack.room_state
  }

  async function createRoom(
    name: string,
    opts: { nsfw?: boolean; query?: QueryInput; source?: string } = {},
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

  async function configureRoom(config: ConfigureRoomPayload): Promise<Ack> {
    return request('configure_room', config)
  }

  async function startGame(): Promise<Ack> {
    if (starting.value) return { ok: false, error: 'game_in_progress' }
    starting.value = true
    try {
      return await request('start_game')
    } finally {
      starting.value = false
    }
  }

  async function stopGame(): Promise<Ack> {
    return request('stop_game')
  }

  async function submitGuess(guess: string): Promise<Ack> {
    if (guessing.value) return { ok: false, error: 'guess_in_flight' }
    guessing.value = true
    try {
      return await request('submit_guess', { guess })
    } finally {
      guessing.value = false
    }
  }

  /**
   * Re-attach to the current room after the socket reconnects. A dropped
   * transport comes back with a fresh server session that has forgotten our
   * membership, so we replay the join exactly as a page refresh would. If the
   * room is gone (torn down while we were away), drop the stale snapshot so the
   * view falls back to the join gate and surfaces the error.
   */
  async function rejoin(): Promise<void> {
    const roomCode = code.value
    const name = useSessionStore().name
    if (!roomCode || !name) return
    const ack = await joinRoom(roomCode, name)
    if (!ack.ok) {
      log.warn('rejoin rejected:', ack.error)
      roomState.value = null
      useGameStore().reset()
      useChatStore().reset()
    }
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
    starting,
    guessing,
    code,
    inProgress,
    nsfw,
    source,
    sources,
    users,
    history,
    winCounts,
    usersWithWins,
    spectators,
    spectatorCount,
    me,
    createRoom,
    joinRoom,
    setReady,
    configureRoom,
    startGame,
    stopGame,
    submitGuess,
    rejoin,
    leaveRoom,
    setRoomState,
    setConnected,
  }
})
