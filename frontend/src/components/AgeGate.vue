<script setup lang="ts">
/**
 * 18+ self-attestation shown before NSFW content. Presentational only — the
 * parent decides what confirm/decline do (attest and reveal, or leave/close).
 * Not real verification; it's the conventional gesture, and the point where each
 * viewer, not just whoever enabled NSFW, gets asked.
 */
withDefaults(defineProps<{ declineLabel?: string }>(), { declineLabel: 'Leave' })
defineEmits<{ confirm: []; decline: [] }>()
</script>

<template>
  <div class="m-auto max-w-md rounded-lg border border-gray-200 p-6 text-center">
    <h2 class="text-lg font-semibold">Adult content</h2>
    <p class="mt-2 text-sm text-gray-500">
      This room is set to show NSFW results from Derpibooru. You must be 18 or
      older to view them.
    </p>
    <div class="mt-5 flex justify-center gap-3">
      <button
        class="rounded border border-gray-300 px-4 py-2 text-sm font-medium hover:bg-gray-50"
        @click="$emit('decline')"
      >
        {{ declineLabel }}
      </button>
      <button
        class="rounded bg-turn px-4 py-2 text-sm font-semibold text-white"
        @click="$emit('confirm')"
      >
        I'm 18 or older
      </button>
    </div>
  </div>
</template>
