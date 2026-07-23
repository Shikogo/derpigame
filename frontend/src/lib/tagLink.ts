/**
 * Links from a tag to the booru search for it, so an unfamiliar tag is one click
 * from an explanation.
 *
 * The search host is per-source: the path is the same across Philomena boorus,
 * but the domain isn't, and it can't be derived from a reveal's `page_url` alone.
 * Callers pass the source the tag came from (the room's or a history round's).
 */

const SEARCH_HOSTS: Record<string, string> = {
  derpibooru: 'https://derpibooru.org/search',
  furbooru: 'https://furbooru.org/search',
}

const DEFAULT_SOURCE = 'derpibooru'

/**
 * The search URL for a tag on a given source. Namespaced tags (`artist:foo`) are
 * valid search terms as-is, so they need no special handling. An unknown source
 * falls back to the default booru rather than producing a broken link.
 */
export function tagSearchUrl(tag: string, source: string = DEFAULT_SOURCE): string {
  const host = SEARCH_HOSTS[source] ?? SEARCH_HOSTS[DEFAULT_SOURCE]
  // URLSearchParams, not encodeURIComponent: it renders a space as "+", which is
  // what a booru search link looks like.
  return `${host}?${new URLSearchParams({ q: tag })}`
}
