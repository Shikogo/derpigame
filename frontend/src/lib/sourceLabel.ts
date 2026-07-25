/**
 * Display name for an image source key, from the server's picker labels.
 *
 * Source keys are server data, so nothing on the client may name a booru: a
 * round played on Furbooru has to say Furbooru. Unknown keys — a source the
 * server has since dropped from the picker — fall back to the capitalized key,
 * which still reads as a name.
 */
import type { SourceOption } from '@/types/wire'

export function sourceLabel(key: string, sources: SourceOption[]): string {
  return sources.find((s) => s.key === key)?.label ?? key.charAt(0).toUpperCase() + key.slice(1)
}
