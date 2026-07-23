/**
 * A thin console wrapper so log calls stay consistent and greppable. `debug` is
 * dev-only; `warn`/`error` always fire, so real failures surface in production
 * too. Route logging through this rather than calling `console` directly.
 */

const PREFIX = '[derpigame]'

export const log = {
  debug: (...args: unknown[]): void => {
    if (import.meta.env.DEV) console.debug(PREFIX, ...args)
  },
  info: (...args: unknown[]): void => console.info(PREFIX, ...args),
  warn: (...args: unknown[]): void => console.warn(PREFIX, ...args),
  error: (...args: unknown[]): void => console.error(PREFIX, ...args),
}
