<script setup lang="ts">
/**
 * Room settings, edited in place in the lobby. There is no draft to apply: each
 * control shows the room's own value and broadcasts via `configure_room` as you
 * change it, so the snapshot stays the single source of truth and another
 * player's edit simply appears. Typed fields follow a beat behind your typing,
 * the rest go on the spot. The pool bounds fold away — set once and left alone.
 */
import { computed, onBeforeUnmount, reactive, ref, watch, type Ref } from 'vue'

import AgeGate from '@/components/AgeGate.vue'
import { useRoomStore } from '@/stores/room'
import { useSessionStore } from '@/stores/session'
import type { ConfigureRoomPayload } from '@/types/wire'

const room = useRoomStore()
const session = useSessionStore()

const state = computed(() => room.roomState)
const axes = computed(() => state.value?.rating_axes ?? [])
const sources = computed(() => state.value?.sources ?? [])

interface TypedField<T> {
  draft: T
  focused: boolean
  /** Typing: sends once you pause, so an edit never waits on you leaving the field. */
  edit: () => void
  /** Blur or Enter: send now, then show what the server made of it. */
  commit: () => Promise<void>
}

/** Long enough not to fire mid-word, short enough to beat anyone's Start press. */
const TYPING_DELAY = 400

/**
 * A field you type into: it can't broadcast per keystroke, so it holds a draft —
 * one that tracks the room while you're out of the field and yields to your text
 * while you're in it. The draft reaches the room a beat after you stop typing,
 * because waiting for a blur means a round can start on the old value while your
 * edit sits on screen looking applied.
 */
function typedField<T>(read: () => T, write: (value: T) => Promise<unknown>): TypedField<T> {
  const draft = ref(read()) as Ref<T>
  const focused = ref(false)
  let pending: ReturnType<typeof setTimeout> | undefined

  watch(read, (value) => {
    if (!focused.value) draft.value = value
  })

  function edit(): void {
    clearTimeout(pending)
    pending = setTimeout(() => void write(draft.value), TYPING_DELAY)
  }

  async function commit(): Promise<void> {
    clearTimeout(pending)
    await write(draft.value)
    // Re-reading normalises the text (`safe,` → `safe`) and snaps back whatever
    // the server clamped or dropped. Right on a deliberate commit, jarring
    // mid-word — which is why the typing path never does it.
    draft.value = read()
  }

  // Nothing to salvage on the way out: the lobby only unmounts for a round
  // starting or a player leaving, and `configure_room` refuses both.
  onBeforeUnmount(() => clearTimeout(pending))

  return reactive({ draft, focused, edit, commit }) as TypedField<T>
}

/** Blank turns a bound off. Tested for emptiness, never truthiness: 0 is a real bound. */
function parseBound(value: number | ''): number | null {
  return value === '' ? null : Math.round(value)
}

function seedBound(value: number | null | undefined): number | '' {
  return value === null || value === undefined ? '' : value
}

const query = typedField(
  () => (state.value?.query ?? []).join(', '),
  (text) => room.configureRoom({ query: text }),
)
const turnSeconds = typedField(
  () => state.value?.turn_seconds ?? 30,
  (seconds) => room.configureRoom({ turn_seconds: seconds }),
)
// A number input's v-model yields '' when the field is empty or unparseable
// (Vue casts numeric inputs implicitly), which is how a bound gets turned off.
const minTagCount = typedField(
  () => seedBound(state.value?.min_tag_count),
  (value) => room.configureRoom({ min_tag_count: parseBound(value) }),
)
const minScore = typedField(
  () => seedBound(state.value?.min_score),
  (value) => room.configureRoom({ min_score: parseBound(value) }),
)

/** Controls that commit the moment you touch them need no draft of their own. */
function configure(config: ConfigureRoomPayload): void {
  void room.configureRoom(config)
}

/**
 * The one box that can't just broadcast: turning NSFW on is where the person
 * doing it attests to being 18+. Mirrored locally rather than bound to the
 * snapshot, because a tick the gate refuses has to be taken back — and a
 * `:checked` reading a snapshot that never changed wouldn't repaint.
 */
const nsfw = ref(state.value?.nsfw ?? false)
const gate = ref<HTMLDialogElement | null>(null)

watch(
  () => state.value?.nsfw ?? false,
  (on) => (nsfw.value = on),
)

function toggleNsfw(on: boolean): void {
  nsfw.value = on
  // Only switching it on needs an answer; switching it off never does.
  if (on && !session.nsfwAck) gate.value?.showModal()
  else configure({ nsfw: on })
}

function attest(): void {
  session.acknowledgeNsfw()
  gate.value?.close()
  configure({ nsfw: true })
}

// Cancel, Escape and a backdrop click all end here — the tick didn't take.
function onGateClose(): void {
  if (!session.nsfwAck) nsfw.value = false
}

// Native <dialog> doesn't dismiss on backdrop click; a click on the element
// itself (not its content) is the backdrop.
function onGateBackdrop(event: MouseEvent): void {
  if (event.target === gate.value) gate.value?.close()
}

/** A cleared cap is dropped rather than sent as a level — that reads as no cap. */
function setCap(key: string, level: string): void {
  const caps = { ...(state.value?.rating_caps ?? {}) }
  if (level) caps[key] = level
  else delete caps[key]
  configure({ rating_caps: caps })
}

/** Every bound and cap, `·`-separated: what the folded row says instead. */
const boundsSummary = computed(() => {
  const snapshot = state.value
  if (!snapshot) return ''
  const parts = [
    snapshot.min_tag_count === null ? 'any tag count' : `${snapshot.min_tag_count}+ tags`,
    snapshot.min_score === null ? 'any score' : `score ${snapshot.min_score}+`,
  ]
  for (const axis of snapshot.rating_axes) {
    const cap = snapshot.rating_caps[axis.key]
    parts.push(`${axis.label.toLowerCase()} ${cap ? `≤ ${cap}` : 'any'}`)
  }
  return parts.join(' · ')
})

/** Taller under `sm` for thumbs; `text-sm` is already 16px on this type scale. */
const field =
  'rounded-lg border border-border bg-raised px-2 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-turn focus:outline-none sm:py-1'

/** A setting on its own row on a phone, label left and control right; inline from `sm`. */
const row = 'flex items-center justify-between gap-2 sm:justify-start'
</script>

<template>
  <section class="flex flex-col gap-3 rounded-lg border border-border bg-surface p-3">
    <h3 class="text-sm font-semibold text-ink-muted">Room settings</h3>

    <label class="flex flex-col gap-1 text-sm">
      <span class="text-ink-muted">Search tags (comma separated)</span>
      <input
        v-model="query.draft"
        name="query"
        placeholder="anything"
        :class="field"
        @focus="query.focused = true"
        @blur="query.focused = false"
        @input="query.edit()"
        @change="query.commit()"
      />
    </label>

    <!-- A stack of rows on a phone, one inline run from `sm` — the wrap the row
         used to do at 360px left the controls in a ragged staircase. -->
    <div class="flex flex-col gap-2 text-sm sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-4">
      <label v-if="sources.length > 1" :class="row">
        <span class="text-ink-muted">Source</span>
        <select
          name="source"
          :value="state?.source"
          class="min-w-0"
          :class="field"
          @change="configure({ source: ($event.target as HTMLSelectElement).value })"
        >
          <option v-for="s in sources" :key="s.key" :value="s.key">{{ s.label }}</option>
        </select>
      </label>

      <label :class="row">
        <span class="text-ink-muted">Seconds per turn</span>
        <input
          v-model.number="turnSeconds.draft"
          name="turn_seconds"
          type="number"
          min="10"
          max="300"
          step="5"
          class="w-20 text-right"
          :class="field"
          @focus="turnSeconds.focused = true"
          @blur="turnSeconds.focused = false"
          @input="turnSeconds.edit()"
          @change="turnSeconds.commit()"
        />
      </label>

      <!-- Reversed under `sm` so the box lands on the right like every other
           control in the stack; back beside its text once the row is inline. -->
      <label class="flex flex-row-reverse items-center justify-between gap-2 sm:flex-row">
        <input
          name="nsfw"
          type="checkbox"
          class="h-5 w-5 shrink-0 accent-turn sm:h-4 sm:w-4"
          :checked="nsfw"
          @change="toggleNsfw(($event.target as HTMLInputElement).checked)"
        />
        <span>Allow NSFW results</span>
      </label>
    </div>

    <dialog
      ref="gate"
      class="m-auto w-[min(28rem,90vw)] bg-transparent p-0 backdrop:bg-black/60"
      @click="onGateBackdrop"
      @close="onGateClose"
    >
      <AgeGate decline-label="Cancel" @confirm="attest" @decline="gate?.close()">
        Turning this on lets the room draw adult images. You must be 18 or older.
      </AgeGate>
    </dialog>

    <!-- Set once and then left alone, so it folds — and closed it reads as the
         summary the lobby used to carry. -->
    <details class="group text-sm">
      <!-- The line wraps rather than ellipsing: the lobby's panel cell is an
           auto grid track, so a `nowrap` summary sizes that track to the whole
           string and pushes the column past a phone's width. -->
      <summary class="flex cursor-pointer list-none items-start gap-2 py-1 text-xs text-ink-faint">
        <span class="shrink-0 transition-transform group-open:rotate-90">▸</span>
        <span>Image pool · {{ boundsSummary }}</span>
      </summary>

      <div class="mt-2 flex flex-col gap-3 rounded-lg border border-border p-3">
        <p class="text-xs text-ink-faint">
          Bounds on the image pool — leave a field blank for no limit.
        </p>

        <label class="flex items-center justify-between gap-2 sm:gap-3">
          <span class="text-ink-muted">Minimum tags</span>
          <input
            v-model="minTagCount.draft"
            name="min_tag_count"
            type="number"
            min="0"
            placeholder="none"
            class="w-24 text-right"
            :class="field"
            @focus="minTagCount.focused = true"
            @blur="minTagCount.focused = false"
            @input="minTagCount.edit()"
            @change="minTagCount.commit()"
          />
        </label>

        <label class="flex items-center justify-between gap-2 sm:gap-3">
          <span class="text-ink-muted">Minimum score</span>
          <input
            v-model="minScore.draft"
            name="min_score"
            type="number"
            placeholder="none"
            class="w-24 text-right"
            :class="field"
            @focus="minScore.focused = true"
            @blur="minScore.focused = false"
            @input="minScore.edit()"
            @change="minScore.commit()"
          />
        </label>

        <label
          v-for="axis in axes"
          :key="axis.key"
          class="flex items-center justify-between gap-2 sm:gap-3"
        >
          <span class="text-ink-muted">{{ axis.label }} up to</span>
          <select
            :name="`cap_${axis.key}`"
            :value="state?.rating_caps?.[axis.key] ?? ''"
            class="w-36 shrink-0 capitalize sm:w-40"
            :class="field"
            @change="setCap(axis.key, ($event.target as HTMLSelectElement).value)"
          >
            <option value="">No limit</option>
            <option v-for="level in axis.levels" :key="level" :value="level">{{ level }}</option>
          </select>
        </label>
      </div>
    </details>
  </section>
</template>
