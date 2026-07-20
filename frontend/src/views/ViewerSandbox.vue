<script setup lang="ts">
/**
 * Dev-only harness for exercising `ImageViewer` in isolation: a bounded frame
 * with a labeled grid image, plus a live readout of the transform so pan / zoom
 * / clamp behavior is verifiable at a glance. Not part of the game UI.
 */
import { ref } from 'vue'

import ImageViewer from '@/components/ImageViewer.vue'

const viewer = ref<InstanceType<typeof ImageViewer> | null>(null)
const src = ref('/viewer-test.svg')
</script>

<template>
  <main class="mx-auto flex max-w-4xl flex-col gap-4 p-6">
    <header class="flex items-center justify-between">
      <h1 class="font-display text-xl font-bold">ImageViewer sandbox</h1>
      <button
        class="rounded bg-turn px-3 py-1.5 text-sm font-medium text-on-accent"
        @click="viewer?.reset()"
      >
        Reset to fit
      </button>
    </header>

    <p class="text-sm text-ink-muted">
      Drag to pan · wheel / trackpad-pinch to zoom toward the cursor · two-finger pinch on touch ·
      double-click to reset. Corners are colored (TL red, TR green, BL blue, BR yellow); cells are
      labeled with their image coordinates.
    </p>

    <!-- A deliberately non-square frame so letterboxing/centering is visible. -->
    <div class="h-[460px] w-full overflow-hidden rounded-lg border border-border">
      <ImageViewer ref="viewer" :src="src" alt="Grid test pattern" />
    </div>

    <pre class="rounded bg-black/60 p-3 font-mono text-xs text-ink" data-testid="view-readout">
scale: {{ viewer?.view.scale.toFixed(3) }}
tx:    {{ viewer?.view.tx.toFixed(1) }}
ty:    {{ viewer?.view.ty.toFixed(1) }}</pre>
  </main>
</template>
