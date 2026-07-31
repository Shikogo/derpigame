<script setup lang="ts">
/**
 * 18+ self-attestation shown before NSFW content. Presentational only — the
 * parent decides what confirm/decline do (attest and reveal, or leave/close) and
 * can replace the body line for what it's asking about. Not real verification;
 * it's the conventional gesture, and the point where each viewer gets asked.
 */
withDefaults(defineProps<{ declineLabel?: string }>(), { declineLabel: 'Leave' })
defineEmits<{ confirm: []; decline: [] }>()
</script>

<template>
  <div
    class="m-auto max-w-md rounded-xl border border-border bg-surface p-6 text-center shadow-2xl"
  >
    <h2 class="font-display text-xl font-bold">Adult content</h2>
    <p class="mt-2 text-sm text-ink-muted">
      <slot>This room is set to show NSFW results. You must be 18 or older to view them.</slot>
    </p>
    <div class="mt-5 flex justify-center gap-3">
      <button
        class="rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-raised"
        @click="$emit('decline')"
      >
        {{ declineLabel }}
      </button>
      <button
        class="rounded-lg bg-turn px-4 py-2 text-sm font-semibold text-on-accent"
        @click="$emit('confirm')"
      >
        I'm 18 or older
      </button>
    </div>
  </div>
</template>
