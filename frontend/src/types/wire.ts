/**
 * The wire contract, mirrored from the backend transport layer.
 *
 * Field names are snake_case to match the Python serializers exactly
 * (`app/service/serialization.py`, `app/transport/snapshots.py`,
 * `app/transport/handlers.py`) — there is no case-translation layer, so these
 * types must track those files.
 */

// --- lobby snapshot (room_state) --------------------------------------------

export interface RoomUser {
  uuid: string
  name: string
  ready: boolean
}

export interface RoomState {
  room: string
  query: string[]
  nsfw: boolean
  in_progress: boolean
  users: RoomUser[]
  history: RoundRecord[]
  win_counts: WinCount[]
}

/**
 * A finished round kept for the lobby history: its Derpibooru link and
 * attribution, plus the result. `aborted` rounds have a link worth keeping but
 * no `winners`/`standings`.
 */
export interface RoundRecord {
  page_url: string
  source_url: string | null
  thumb_url: string
  artists: string[]
  win: boolean
  aborted: boolean
  winners: Player[]
  standings: Player[]
}

/** Server-computed running win count for one player, most wins first in the list. */
export interface WinCount {
  uuid: string
  name: string
  wins: number
}

// --- game events (game_events channel: a batched list) ----------------------

export interface Player {
  uuid: string
  name: string
  score: number
  wrong_guesses: number
}

/** Why a guess was a no-op (never a strike). Matches the domain `RejectReason`. */
export type RejectReason = 'already_guessed' | 'already_wrong' | 'default_tag' | 'rating_tag'

/**
 * A taxonomy bucket key, e.g. "tags" or "artists". The set is defined by the
 * backend's `TagTaxonomy` and varies per source (e621 adds character/species/…),
 * so it's an opaque string here — never hardcode the possible values.
 */
export type BucketKey = string

export interface GameStarted {
  type: 'game_started'
  first_player: Player
  /** The full roster for the round; room members not in it are spectators. */
  players: Player[]
  /** Goal-bucket tags — all must be guessed to win. */
  tag_count: number
  /** Namespaced bonus buckets, keyed by bucket, e.g. { artists: 1, ocs: 2 }. */
  bonus_counts: Record<BucketKey, number>
  query: string[]
  turn_seconds: number
}

export interface TurnStarted {
  type: 'turn_started'
  player: Player
}

export interface GuessRejected {
  type: 'guess_rejected'
  guess: string
  reason: RejectReason
}

export interface CorrectGuess {
  type: 'correct_guess'
  player: Player
  guess: string
  tag_type: BucketKey
  /** Tags left in the bucket this guess landed in. */
  remaining: number
}

export interface WrongGuess {
  type: 'wrong_guess'
  player: Player
  guess: string
  wrong_count: number
  /** Similarity %, 0 when not a near miss. */
  closeness: number
}

export interface Timeout {
  type: 'timeout'
  player: Player
  wrong_count: number
}

export interface PlayerEliminated {
  type: 'player_eliminated'
  player: Player
}

export interface GameOver {
  type: 'game_over'
  win: boolean
  winners: Player[]
  standings: Player[]
  /** Unguessed goal-bucket tags (not bonus buckets). */
  unguessed_tags: string[]
}

// Service-composed payloads (plain dicts, not domain events).

export interface NoImage {
  type: 'no_image'
  query: string[]
}

export interface ImageError {
  type: 'image_error'
}

export interface GameAborted {
  type: 'game_aborted'
}

/** The picture to display — deliberately without any answer-revealing tags. */
export interface ImageStarted {
  type: 'image_started'
  id: string
  thumb_url: string
  full_url: string
}

/** Attribution, revealed once the image is no longer a secret (game end/abort). */
export interface ImageRevealed {
  type: 'image_revealed'
  artists: string[]
  source_url: string | null
  page_url: string
}

/**
 * Answer-safe state of a round in progress, sent only to a (re)joining socket so
 * a reload / late join can render the live game. Counts and scores only — never
 * the unguessed goal tags.
 */
export interface GameSnapshot {
  type: 'game_snapshot'
  image: { id: string; thumb_url: string; full_url: string }
  players: Player[]
  active_player: Player
  /** Original goal-bucket size (the progress denominator). */
  tag_count: number
  goal_remaining: number
  bonus_counts: Record<BucketKey, number>
  /** uuids of players already eliminated this round. */
  eliminated: string[]
  turn_seconds: number
}

export type GameEvent =
  | GameStarted
  | TurnStarted
  | GuessRejected
  | CorrectGuess
  | WrongGuess
  | Timeout
  | PlayerEliminated
  | GameOver
  | NoImage
  | ImageError
  | GameAborted
  | ImageStarted
  | ImageRevealed
  | GameSnapshot

/** Discriminator string of every game event, for exhaustive reducer switches. */
export type GameEventType = GameEvent['type']

// --- chat (social side-channel) ---------------------------------------------

export interface ChatMessage {
  name: string
  text: string
}

// --- ack callbacks (per-caller replies) -------------------------------------

export interface OkAck {
  ok: true
  /** Present on create_room / join_room. */
  room_state?: RoomState
}

export interface ErrAck {
  ok: false
  error: string
  /** Present on a not_your_turn rejection. */
  active_player?: { uuid: string; name: string }
}

export type Ack = OkAck | ErrAck

// --- client -> server payloads ----------------------------------------------

/** A query is sent as tags; the backend also accepts a comma/newline string. */
export type QueryInput = string[] | string

export interface CreateRoomPayload {
  name: string
  uuid: string
  nsfw?: boolean
  query?: QueryInput
}

export interface JoinRoomPayload {
  room: string
  name: string
  uuid: string
}

export interface SetReadyPayload {
  ready: boolean
}

export interface ConfigureRoomPayload {
  query?: QueryInput
  nsfw?: boolean
}

export interface SubmitGuessPayload {
  guess: string
}

export interface ChatPayload {
  text: string
}
