/**
 * Restore the Web Storage globals under Node >= 22.
 *
 * Node ships its own experimental `localStorage`/`sessionStorage` on
 * `globalThis`, inert unless started with `--localstorage-file`. Vitest's jsdom
 * environment only installs a jsdom global when the key is absent from
 * `globalThis` or on its own curated list (`getWindowKeys`), and Web Storage is
 * on neither — so Node's inert stub wins and every `localStorage` call in a test
 * reads `undefined`.
 *
 * Vitest exposes the real jsdom instance as `globalThis.jsdom`, so we can put
 * the working implementations back. Drop this file once Vitest handles the
 * collision itself.
 */

const jsdomWindow = (globalThis as { jsdom?: { window: Window } }).jsdom?.window

if (jsdomWindow) {
  for (const key of ['localStorage', 'sessionStorage'] as const) {
    Object.defineProperty(globalThis, key, {
      value: jsdomWindow[key],
      configurable: true,
      writable: true,
    })
  }
}
