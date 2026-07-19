/** Map the backend's ack error strings to human-readable UI messages. */
const LABELS: Record<string, string> = {
  room_not_found: 'No room with that code.',
  name_taken: 'That name is taken in this room.',
  not_ready: 'Ready up before you can start the game.',
  not_your_turn: 'It’s not your turn.',
  game_in_progress: 'A game is already in progress.',
  bad_request: 'Enter a name (and a code to join).',
  room_unavailable: 'Could not open a room. Try again.',
  not_in_room: 'You’re not in this room.',
  timeout: 'The server didn’t respond — check your connection.',
}

export function errorLabel(error: string | null | undefined): string {
  if (!error) return ''
  return LABELS[error] ?? error
}
