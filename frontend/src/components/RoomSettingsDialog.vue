<script setup lang="ts">
/**
 * Modal editor for room settings (search tags, NSFW, turn length, and the
 * search bounds). Seeds from the current snapshot when opened; applying
 * broadcasts via `configure_room`, so every player's lobby summary updates.
 * Closing without Apply discards the edits.
 */
import { computed, ref } from 'vue'

import { useRoomStore } from '@/stores/room'

const room = useRoomStore()

const dialog = ref<HTMLDialogElement | null>(null)
const queryText = ref('')
const nsfw = ref(false)
const source = ref('derpibooru')
const turnSeconds = ref(30)
// A number input's v-model yields '' when the field is empty or unparseable
// (Vue casts numeric inputs implicitly), which is how a bound gets turned off.
const minTagCount = ref<number | ''>('')
const minScore = ref<number | ''>('')
const caps = ref<Record<string, string>>({})

const axes = computed(() => room.roomState?.rating_axes ?? [])
const sources = computed(() => room.roomState?.sources ?? [])

/** Blank turns a bound off. Tested for emptiness, never truthiness: 0 is a real bound. */
function parseBound(value: number | ''): number | null {
  return value === '' ? null : Math.round(value)
}

function seedBound(value: number | null | undefined): number | '' {
  return value === null || value === undefined ? '' : value
}

function open(): void {
  const state = room.roomState
  queryText.value = (state?.query ?? []).join(', ')
  nsfw.value = state?.nsfw ?? false
  source.value = state?.source ?? 'derpibooru'
  turnSeconds.value = state?.turn_seconds ?? 30
  minTagCount.value = seedBound(state?.min_tag_count)
  minScore.value = seedBound(state?.min_score)
  // Every axis gets a key so `v-model` has something to bind; '' is uncapped.
  caps.value = Object.fromEntries(
    axes.value.map((axis) => [axis.key, state?.rating_caps?.[axis.key] ?? '']),
  )
  dialog.value?.showModal()
}

function close(): void {
  dialog.value?.close()
}

function apply(): void {
  room.configureRoom({
    query: queryText.value,
    nsfw: nsfw.value,
    source: source.value,
    turn_seconds: turnSeconds.value,
    min_tag_count: parseBound(minTagCount.value),
    min_score: parseBound(minScore.value),
    rating_caps: Object.fromEntries(Object.entries(caps.value).filter(([, level]) => level !== '')),
  })
  close()
}

// Native <dialog> doesn't dismiss on backdrop click; a click on the element
// itself (not its content) is the backdrop.
function onBackdrop(event: MouseEvent): void {
  if (event.target === dialog.value) close()
}

defineExpose({ open })
</script>

<template>
  <dialog
    ref="dialog"
    class="m-auto w-[min(28rem,90vw)] rounded-xl border border-border bg-surface p-0 text-ink shadow-2xl backdrop:bg-black/60"
    @click="onBackdrop"
  >
    <form class="flex flex-col gap-4 p-5" @submit.prevent="apply">
      <h2 class="font-display text-xl font-bold">Room settings</h2>

      <label class="flex flex-col gap-1 text-sm">
        <span class="text-ink-muted">Search tags (comma or newline separated)</span>
        <textarea
          v-model="queryText"
          name="query"
          rows="3"
          placeholder="e.g. safe, pony"
          class="resize-y rounded-lg border border-border bg-raised px-2 py-1 text-sm text-ink placeholder:text-ink-faint focus:border-turn focus:outline-none"
        />
      </label>

      <label v-if="sources.length > 1" class="flex items-center justify-between gap-3 text-sm">
        <span class="text-ink-muted">Image source</span>
        <select
          v-model="source"
          name="source"
          class="w-40 rounded-lg border border-border bg-raised px-2 py-1 text-sm text-ink focus:border-turn focus:outline-none"
        >
          <option v-for="s in sources" :key="s.key" :value="s.key">{{ s.label }}</option>
        </select>
      </label>

      <label class="flex items-center justify-between gap-3 text-sm">
        <span class="text-ink-muted">Seconds per turn</span>
        <input
          v-model.number="turnSeconds"
          name="turn_seconds"
          type="number"
          min="10"
          max="300"
          step="5"
          class="w-24 rounded-lg border border-border bg-raised px-2 py-1 text-right text-sm text-ink focus:border-turn focus:outline-none"
        />
      </label>

      <div class="flex flex-col gap-3 rounded-lg border border-border p-3">
        <p class="text-xs text-ink-faint">
          Bounds on the image pool — leave a field blank for no limit.
        </p>

        <label class="flex items-center justify-between gap-3 text-sm">
          <span class="text-ink-muted">Minimum tags</span>
          <input
            v-model="minTagCount"
            name="min_tag_count"
            type="number"
            min="0"
            placeholder="none"
            class="w-24 rounded-lg border border-border bg-raised px-2 py-1 text-right text-sm text-ink placeholder:text-ink-faint focus:border-turn focus:outline-none"
          />
        </label>

        <label class="flex items-center justify-between gap-3 text-sm">
          <span class="text-ink-muted">Minimum score</span>
          <input
            v-model="minScore"
            name="min_score"
            type="number"
            placeholder="none"
            class="w-24 rounded-lg border border-border bg-raised px-2 py-1 text-right text-sm text-ink placeholder:text-ink-faint focus:border-turn focus:outline-none"
          />
        </label>

        <label
          v-for="axis in axes"
          :key="axis.key"
          class="flex items-center justify-between gap-3 text-sm"
        >
          <span class="text-ink-muted">{{ axis.label }} up to</span>
          <select
            v-model="caps[axis.key]"
            :name="`cap_${axis.key}`"
            class="w-40 rounded-lg border border-border bg-raised px-2 py-1 text-sm capitalize text-ink focus:border-turn focus:outline-none"
          >
            <option value="">No limit</option>
            <option v-for="level in axis.levels" :key="level" :value="level">{{ level }}</option>
          </select>
        </label>
      </div>

      <label class="flex items-center gap-2 text-sm">
        <input v-model="nsfw" name="nsfw" type="checkbox" class="accent-turn" />
        Allow NSFW results
      </label>

      <div class="flex justify-end gap-2">
        <button
          type="button"
          class="rounded-lg border border-border px-3 py-1.5 text-sm font-medium hover:bg-raised"
          @click="close"
        >
          Cancel
        </button>
        <button
          type="submit"
          class="rounded-lg bg-turn px-4 py-1.5 text-sm font-semibold text-on-accent"
        >
          Apply
        </button>
      </div>
    </form>
  </dialog>
</template>
