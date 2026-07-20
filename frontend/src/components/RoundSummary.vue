<script setup lang="ts">
/**
 * The end-of-round tag recap: what the room found, what it missed grouped by
 * taxonomy bucket, and the wrong guesses as tagging suggestions. Shown for a
 * finished round and a stopped one alike.
 */
import { computed } from 'vue'

import { foundTags, missedGroups, suggestedTags } from '@/game/roundSummary'
import { bucketColor, bucketPillStyle } from '@/lib/tagColor'
import { tagSearchUrl } from '@/lib/tagLink'
import { useGameStore } from '@/stores/game'

const game = useGameStore()

const found = computed(() => foundTags(game.state))
const missed = computed(() => missedGroups(game.state))
const missedCount = computed(() => missed.value.reduce((n, g) => n + g.tags.length, 0))
const suggested = computed(() => suggestedTags(game.state))
const bucketKeys = computed(() => Object.keys(game.state.bonusCounts))
</script>

<template>
  <div v-if="found.length || missedCount || suggested.length" class="flex flex-col gap-4">
    <section v-if="found.length" class="flex flex-col gap-2">
      <h3 class="text-sm font-semibold">
        Found <span class="font-mono text-ink-faint tabular-nums">{{ found.length }}</span>
      </h3>
      <div class="flex flex-wrap gap-1.5">
        <a
          v-for="(t, i) in found"
          :key="`${t.tag}-${i}`"
          :href="tagSearchUrl(t.tag)"
          target="_blank"
          rel="noopener noreferrer"
          class="pill hover:underline"
          :class="t.player ? 'bg-correct/10 text-correct' : 'bg-raised text-ink-faint'"
        >
          {{ t.tag }}
          <span class="font-normal opacity-70">{{ t.player ?? 'free' }}</span>
        </a>
      </div>
    </section>

    <section v-if="missedCount" class="flex flex-col gap-2">
      <h3 class="text-sm font-semibold">
        Missed <span class="font-mono text-ink-faint tabular-nums">{{ missedCount }}</span>
      </h3>
      <!-- Bucket keys are opaque (source-defined taxonomy) — render them as-is. -->
      <div
        v-for="group in missed"
        :key="group.bucket"
        class="flex flex-col gap-1.5 sm:flex-row sm:items-baseline sm:gap-3"
      >
        <span
          class="font-mono text-xs uppercase sm:w-16 sm:shrink-0 sm:text-right"
          :style="{ color: bucketColor(group.bucket, bucketKeys) }"
        >
          {{ group.bucket }}
        </span>
        <div class="flex flex-wrap gap-1.5">
          <a
            v-for="tag in group.tags"
            :key="tag"
            :href="tagSearchUrl(tag)"
            target="_blank"
            rel="noopener noreferrer"
            class="pill hover:underline"
            :style="bucketPillStyle(group.bucket, bucketKeys)"
          >
            {{ tag }}
          </a>
        </div>
      </div>
    </section>

    <!-- Wrong guesses turned useful: a dashed pill reads as "not on the image
         (yet)", so it can't be mistaken for the found or missed answer key. -->
    <section v-if="suggested.length" class="flex flex-col gap-2">
      <h3 class="text-sm font-semibold">
        Consider adding
        <span class="font-mono text-ink-faint tabular-nums">{{ suggested.length }}</span>
      </h3>
      <p class="text-xs text-ink-faint">
        These guesses didn't match the image. Consider adding them if they fit!
      </p>
      <div class="flex flex-wrap gap-1.5">
        <span
          v-for="(t, i) in suggested"
          :key="`${t.tag}-${i}`"
          class="pill border border-dashed border-border text-ink-faint"
        >
          {{ t.tag }}
          <span class="font-normal opacity-70">{{ t.player }}</span>
        </span>
      </div>
    </section>
  </div>
</template>
