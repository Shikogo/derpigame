<script setup lang="ts">
/**
 * The rail's lower half. On `lg` it's a plain column in the rail. Below `lg`,
 * while a round is live (`docked`), it becomes a sheet over the game: the
 * picture and the guess box own the screen, and the log and chat are one tap
 * away.
 *
 * `docked` isn't a breakpoint test — every mobile class here is `max-lg:`. It's
 * "is the room running its fixed shell", so the lobby and results screens, which
 * still scroll, get a plain column at every width.
 */
import { onBeforeUnmount, watch } from 'vue'

const props = defineProps<{ docked: boolean; open: boolean }>()
const emit = defineEmits<{ 'update:open': [boolean] }>()

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') emit('update:open', false)
}

// Only while it's a sheet: on desktop there's nothing open to escape from, and
// Escape belongs to whatever dialog is up instead.
// `immediate` because a sheet can mount already open — the room re-renders one
// mid-round when the panel behind it swaps.
watch(
  () => props.docked && props.open,
  (sheet) => {
    if (sheet) window.addEventListener('keydown', onKeydown)
    else window.removeEventListener('keydown', onKeydown)
  },
  { immediate: true },
)

onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <!-- A tap-anywhere-to-close target, deliberately not a dim: the picture above
       the sheet is the thing you keep open the sheet to look at, and darkening
       it is the one thing this layout exists to avoid. The sheet reads as on top
       from its own surface and shadow.

       Teleported so the shell's `overflow-hidden` can't clip it. -->
  <Teleport to="body" :disabled="!docked">
    <div
      v-if="docked && open"
      class="fixed inset-0 z-30 lg:hidden"
      @click="emit('update:open', false)"
    />
  </Teleport>

  <!-- `invisible` rather than v-show/inert: it takes the closed sheet out of the
       tab order and the accessibility tree, and being `max-lg:`-scoped it can
       never touch the desktop rail. Naming `visibility` in the transition is
       what flips it at the end of the slide down and at the start of the slide
       up, instead of blanking the sheet the moment it starts moving.

       The keyboard inset is the sheet's floor and its ceiling: the box sits on
       top of the keys, and the height it may take is what's left above them. A
       sheet sized off the full viewport would run off the top of the screen the
       moment the chat box was focused.

       Not a scroll container. Its children divide a definite height between them
       and scroll their own contents, which is what keeps the chat box pinned to
       the bottom edge instead of somewhere below the fold. -->
  <div
    id="round-sheet"
    class="flex min-h-0 flex-col gap-4"
    :class="
      docked && [
        'max-lg:fixed max-lg:inset-x-0 max-lg:bottom-[var(--kbd-inset,0px)] max-lg:z-40',
        'max-lg:h-[min(70dvh,calc(100dvh-var(--kbd-inset,0px)-4rem))]',
        'max-lg:rounded-t-2xl max-lg:border-t max-lg:border-border max-lg:bg-surface max-lg:p-3 max-lg:shadow-2xl',
        'max-lg:transition-[transform,visibility] max-lg:duration-300',
        open ? 'max-lg:translate-y-0' : 'max-lg:invisible max-lg:translate-y-full',
      ]
    "
  >
    <slot />
  </div>
</template>
