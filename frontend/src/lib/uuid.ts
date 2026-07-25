/**
 * A v4 uuid that also works off https.
 *
 * `crypto.randomUUID` is secure-context only, so it's missing when the app is
 * served from a LAN address over plain http — which is how the game gets tested
 * on a phone. `crypto.getRandomValues` has no such restriction, so fall back to
 * assembling the uuid from it.
 */
export function randomUuid(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()

  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40 // version 4
  bytes[8] = (bytes[8] & 0x3f) | 0x80 // variant 10xx
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')

  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20),
  ].join('-')
}
