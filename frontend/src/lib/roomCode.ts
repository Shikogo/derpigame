/**
 * Where the room code lives when the URL can't hold it.
 *
 * Streamer mode strips the code from the address bar, so the tab has to
 * remember which room it's in for a refresh to land back there.
 * `sessionStorage` rather than `localStorage` on purpose: it's per-tab and dies
 * with the tab, which is exactly the lifetime of "the room this tab is in".
 */

import type { RouteLocationRaw } from 'vue-router'

const ROOM_KEY = 'derpigame:room'

/** Codes are adjective-adjective-noun; the mask keeps the shape, not the words. */
export const MASKED_CODE = '•••-•••-•••'

export function rememberRoom(code: string, storage: Storage = sessionStorage): void {
  storage.setItem(ROOM_KEY, code)
}

export function recallRoom(storage: Storage = sessionStorage): string | null {
  return storage.getItem(ROOM_KEY)
}

export function forgetRoom(storage: Storage = sessionStorage): void {
  storage.removeItem(ROOM_KEY)
}

/** The room route, with the code left out of the URL while it's hidden. */
export function roomRoute(code: string, hidden: boolean): RouteLocationRaw {
  return { name: 'room', params: { code: hidden ? '' : code } }
}
