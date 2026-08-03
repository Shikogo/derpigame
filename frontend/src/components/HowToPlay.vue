<script setup lang="ts">
/**
 * The rules, shown once on a browser's first visit and on demand after that.
 * Presentational only — the parent decides how it's shown and what closing does.
 */
import { KOFI_URL } from '@/lib/links'

defineEmits<{ close: [] }>()
</script>

<template>
  <div
    class="m-auto max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-xl border border-border bg-surface p-6 text-ink shadow-2xl"
  >
    <h2 class="font-display text-xl font-bold">How to play</h2>

    <dl class="mt-4 space-y-4 text-sm">
      <div>
        <dt class="font-semibold">Concept</dt>
        <dd class="mt-1 text-ink-muted">
          Each round, a random picture from Derpibooru is picked. Everyone tries to guess the tags
          it has. Whoever guesses the most tags wins!
        </dd>
      </div>

      <div>
        <dt class="font-semibold">Turns</dt>
        <dd class="mt-1 text-ink-muted">
          Players take turns, each turn you get to guess one tag. There's a time limit, and if you
          time out, that's a strike! Three strikes and you're out. The game continues until everyone
          is eliminated or every required tag has been guessed.
        </dd>
      </div>

      <div>
        <dt class="font-semibold">Scoring</dt>
        <dd class="mt-1 text-ink-muted">
          Each tag is worth 1 point. Some tags (e.g. the names of artists, OCs and fanfics) are
          optional - they don't count towards total tag count, but can still be guessed! Some tags
          (e.g. rating tags) can't be guessed. You don't lose your turn for guessing them.
        </dd>
      </div>
    </dl>

    <div class="mt-6 flex items-center justify-between gap-4">
      <a
        :href="KOFI_URL"
        target="_blank"
        rel="noopener noreferrer"
        class="text-xs text-ink-faint underline transition-colors hover:text-ink-muted"
      >
        Buy me a coffee ☕
      </a>
      <button
        autofocus
        class="rounded-lg bg-turn px-4 py-2 text-sm font-semibold text-on-accent"
        @click="$emit('close')"
      >
        Close
      </button>
    </div>
  </div>
</template>
