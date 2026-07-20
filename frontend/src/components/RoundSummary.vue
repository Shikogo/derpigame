<script setup lang="ts">
/**
 * The end-of-round tag recap: what the room found, and what it missed grouped
 * by taxonomy bucket. Shown for a finished round and a stopped one alike.
 */
import { computed } from 'vue'

import { foundTags, missedGroups } from '@/game/roundSummary'
import { categoryColor, categoryPillStyle } from '@/lib/tagColor'
import { useGameStore } from '@/stores/game'

const game = useGameStore()

const found = computed(() => foundTags(game.state))
const missed = computed(() => missedGroups(game.state))
const missedCount = computed(() => missed.value.reduce((n, g) => n + g.tags.length, 0))
</script>

<template>
  <div v-if="found.length || missedCount" class="flex flex-col gap-4">
    <section v-if="found.length" class="flex flex-col gap-2">
      <h3 class="text-sm font-semibold">
        Found <span class="font-mono text-ink-faint tabular-nums">{{ found.length }}</span>
      </h3>
      <div class="flex flex-wrap gap-1.5">
        <span
          v-for="(t, i) in found"
          :key="`${t.tag}-${i}`"
          class="pill"
          :class="t.player ? 'bg-correct/10 text-correct' : 'bg-raised text-ink-faint'"
        >
          {{ t.tag }}
          <span class="font-normal opacity-70">{{ t.player ?? 'free' }}</span>
        </span>
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
          :style="{ color: categoryColor(group.bucket) }"
        >
          {{ group.bucket }}
        </span>
        <div class="flex flex-wrap gap-1.5">
          <span
            v-for="tag in group.tags"
            :key="tag"
            class="pill"
            :style="categoryPillStyle(group.bucket)"
          >
            {{ tag }}
          </span>
        </div>
      </div>
    </section>
  </div>
</template>
