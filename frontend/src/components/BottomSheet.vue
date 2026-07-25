<script setup lang="ts">
/**
 * The rail's lower half, mounted only while a round is on screen. On `lg` it's a
 * plain column in the rail. Below `lg` it's a sheet over the game: the picture
 * and the guess box own the screen, and the round log is one tap away.
 */
import { onBeforeUnmount, watch } from 'vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [boolean] }>()

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') emit('update:open', false)
}

// `immediate` because the sheet can mount already open — the room re-renders one
// mid-round when the panel behind it swaps.
watch(
  () => props.open,
  (open) => {
    if (open) window.addEventListener('keydown', onKeydown)
    else window.removeEventListener('keydown', onKeydown)
  },
  { immediate: true },
)

onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <!-- A tap-anywhere-to-close target, deliberately not a dim: the picture above
       the sheet is the thing you open the sheet next to, and darkening it is the
       one thing this layout exists to avoid. The sheet reads as on top from its
       own surface and shadow.

       Teleported so the shell's `overflow-hidden` can't clip it. -->
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-30 lg:hidden" @click="emit('update:open', false)" />
  </Teleport>

  <!-- `invisible` rather than v-show/inert: it takes the closed sheet out of the
       tab order and the accessibility tree, and being `max-lg:`-scoped it can
       never touch the desktop rail. Naming `visibility` in the transition is
       what flips it at the end of the slide down and at the start of the slide
       up, instead of blanking the sheet the moment it starts moving.

       Nothing in here takes focus, so the keyboard is only ever up from the guess
       box behind it. The inset still bounds the sheet — it sits above the keys and
       takes what's left above them — so opening it mid-typing can't land it behind
       the keyboard or run it off the top.

       It scrolls itself, so its contents can be any length: in the rail it takes
       what the strip and the dock leave, and as a sheet it grows with the round
       up to a cap — a `max-h`, so early on it's a short card over the picture
       rather than a mostly-empty panel. -->
  <div
    id="round-sheet"
    class="flex min-h-0 flex-col gap-4 lg:flex-1 lg:overflow-y-auto"
    :class="[
      'max-lg:fixed max-lg:inset-x-0 max-lg:bottom-[var(--kbd-inset,0px)] max-lg:z-40',
      'max-lg:max-h-[min(70dvh,calc(100dvh-var(--kbd-inset,0px)-4rem))]',
      'max-lg:overflow-y-auto max-lg:overscroll-contain',
      'max-lg:rounded-t-2xl max-lg:border-t max-lg:border-border max-lg:bg-surface max-lg:p-3 max-lg:shadow-2xl',
      'max-lg:transition-[transform,visibility] max-lg:duration-300',
      open ? 'max-lg:translate-y-0' : 'max-lg:invisible max-lg:translate-y-full',
    ]"
  >
    <slot />
  </div>
</template>
