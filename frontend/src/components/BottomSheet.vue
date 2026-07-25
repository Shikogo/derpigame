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
  <!-- Tap anywhere to close. Transparent, not a dim: the picture behind is what
       you opened the sheet next to.

       Sibling of the sheet so the two order against each other: the mobile shell
       makes `main` a stacking context, which keeps the sheet's z-index local to
       it. Anything above from outside would swallow every tap meant for it. -->
  <div v-if="open" class="fixed inset-0 z-30 lg:hidden" @click="emit('update:open', false)" />

  <!-- `invisible` rather than v-show/inert: it drops the closed sheet from the
       tab order and the a11y tree, and naming `visibility` in the transition
       flips it at the ends of the slide rather than the moment it starts.

       The keyboard inset bounds it, so opening it mid-typing lands it above the
       keys. It scrolls itself and grows with the round up to a `max-h`, so an
       early round is a short card over the picture, not a half-empty panel. -->
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
