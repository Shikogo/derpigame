/**
 * Links from a tag to the booru search for it, so an unfamiliar tag is one click
 * from an explanation.
 *
 * Derpibooru-specific by necessity: the search path is per-site, so this can't be
 * derived from the reveal's `page_url` origin alone. When e621 lands as a second
 * `ImageSource`, the round will need to say which source it came from and this
 * becomes a lookup keyed on that.
 */

const DERPIBOORU_SEARCH = 'https://derpibooru.org/search'

/**
 * The search URL for a tag. Namespaced tags (`artist:foo`) are valid search
 * terms as-is, so they need no special handling.
 */
export function tagSearchUrl(tag: string): string {
  // URLSearchParams, not encodeURIComponent: it renders a space as "+", which is
  // what a booru search link looks like.
  return `${DERPIBOORU_SEARCH}?${new URLSearchParams({ q: tag })}`
}
