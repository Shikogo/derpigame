<script setup lang="ts">
/**
 * Bounded pan/zoom image frame. Drag to pan, wheel / trackpad-pinch / two-finger
 * pinch to zoom toward the pointer, double-click to reset to fit — plus on-screen
 * controls, since none of those gestures announce themselves. All the math is in
 * `@/lib/viewerGeometry`; this component owns the reactive view and turns
 * pointer/wheel events into geometry calls.
 *
 * Edges are elastic: a drag can pull the image past the frame with rubber-band
 * resistance, then springs back to the hard bound on release.
 *
 * Booru images run to tens of megabytes, so the picture stays hidden behind a
 * spinner until it has fully decoded — otherwise the browser paints the partial
 * image under a stale transform, which reads as a flash of the top-left corner.
 */
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

import IconFit from '@/components/icons/IconFit.vue'
import IconZoomIn from '@/components/icons/IconZoomIn.vue'
import IconZoomOut from '@/components/icons/IconZoomOut.vue'
import {
  ZOOM_STEP,
  clampScale,
  clampTranslate,
  fitView,
  isFitted,
  isMaxZoomed,
  panBy,
  pictureTop,
  zoomPercent,
  zoomToPoint,
  type Size,
  type View,
} from '@/lib/viewerGeometry'

const props = defineProps<{ src: string; alt?: string }>()

const frameEl = ref<HTMLElement | null>(null)
const imageEl = ref<HTMLImageElement | null>(null)
const frame = reactive<Size>({ width: 0, height: 0 })
const image = reactive<Size>({ width: 0, height: 0 })
const view = reactive<View>({ scale: 1, tx: 0, ty: 0 })
const settling = ref(false) // animate transform back to bounds after a release
const loading = ref(true)
const slow = ref(false) // loading long enough to be worth announcing
const failed = ref(false)
const dragging = ref(false)
const showHint = ref(false)

const ready = computed(() => !loading.value && !failed.value)
const fitted = computed(() => isFitted(view, frame, image))
const maxed = computed(() => isMaxZoomed(view, frame, image))
const percent = computed(() => zoomPercent(view, frame, image))
// Where the picture actually starts, so a caller's overlay can attach to it
// rather than to the frame.
const contentTop = computed(() => pictureTop(view))

const pointers = new Map<number, { x: number; y: number }>()
let pinchDist = 0
let settleTimer: ReturnType<typeof setTimeout> | undefined
let hintTimer: ReturnType<typeof setTimeout> | undefined
let slowTimer: ReturnType<typeof setTimeout> | undefined
let hintOffered = false

/**
 * Begin a load. The picture is hidden immediately, but the spinner waits — a
 * cached image (the reveal screen re-showing the round's picture) resolves in
 * well under this, and a spinner that flashes for one frame just looks broken.
 */
function beginLoad(): void {
  loading.value = true
  failed.value = false
  slow.value = false
  clearTimeout(slowTimer)
  slowTimer = setTimeout(() => (slow.value = true), 150)
}

function endLoad(): void {
  clearTimeout(slowTimer)
  loading.value = false
  slow.value = false
}

/** How far a drag may pull the image past an edge before resistance caps it. */
function give(): number {
  return 0.15 * Math.min(frame.width, frame.height)
}

function apply(next: View): void {
  view.scale = next.scale
  view.tx = next.tx
  view.ty = next.ty
}

/** Animate to a target (spring-back on release, or reset-to-fit). */
function animateTo(target: View): void {
  settling.value = true
  apply(target)
  clearTimeout(settleTimer)
  settleTimer = setTimeout(() => (settling.value = false), 220)
}

function stopSettling(): void {
  clearTimeout(settleTimer)
  settling.value = false
}

function reset(): void {
  dismissHint()
  animateTo(fitView(frame, image))
}

/** One notch of button zoom, about the middle of the frame. */
function zoomBy(factor: number): void {
  dismissHint()
  stopSettling()
  const center = { x: frame.width / 2, y: frame.height / 2 }
  animateTo(zoomToPoint(view, view.scale * factor, center, frame, image))
}

/**
 * Spell the gestures out the first time this viewer shows a picture, then get
 * out of the way — on interaction, or on a timer for anyone who never tries.
 */
function offerHint(): void {
  if (hintOffered) return
  hintOffered = true
  showHint.value = true
  hintTimer = setTimeout(() => (showHint.value = false), 7000)
}

function dismissHint(): void {
  clearTimeout(hintTimer)
  showHint.value = false
}

/** After a gesture, ease any elastic overshoot back to the hard bounds. */
function settle(): void {
  const target = clampTranslate(view, frame, image)
  if (target.tx !== view.tx || target.ty !== view.ty) animateTo(target)
}

function localPoint(clientX: number, clientY: number) {
  const rect = frameEl.value?.getBoundingClientRect()
  return { x: clientX - (rect?.left ?? 0), y: clientY - (rect?.top ?? 0) }
}

function onImageLoad(): void {
  const img = imageEl.value
  if (!img?.naturalWidth) return
  image.width = img.naturalWidth
  image.height = img.naturalHeight
  apply(fitView(frame, image))
  endLoad()
  offerHint()
}

function onImageError(): void {
  endLoad()
  failed.value = true
}

function onWheel(e: WheelEvent): void {
  e.preventDefault()
  dismissHint()
  stopSettling()
  const factor = Math.exp(-e.deltaY * 0.0015)
  apply(zoomToPoint(view, view.scale * factor, localPoint(e.clientX, e.clientY), frame, image))
}

function onPointerDown(e: PointerEvent): void {
  ;(e.target as Element).setPointerCapture(e.pointerId)
  dismissHint()
  stopSettling()
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
  pinchDist = 0
  dragging.value = true
}

function onPointerMove(e: PointerEvent): void {
  const prev = pointers.get(e.pointerId)
  if (!prev) return
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })

  const points = [...pointers.values()]
  if (points.length >= 2) {
    pinch(points[0], points[1])
  } else {
    apply(panBy(view, e.clientX - prev.x, e.clientY - prev.y, frame, image, give()))
  }
}

function pinch(a: { x: number; y: number }, b: { x: number; y: number }): void {
  const dist = Math.hypot(a.x - b.x, a.y - b.y)
  const mid = localPoint((a.x + b.x) / 2, (a.y + b.y) / 2)
  if (pinchDist > 0 && dist > 0) {
    apply(zoomToPoint(view, view.scale * (dist / pinchDist), mid, frame, image, give()))
  }
  pinchDist = dist
}

function onPointerUp(e: PointerEvent): void {
  pointers.delete(e.pointerId)
  if (pointers.size < 2) pinchDist = 0
  if (pointers.size === 0) {
    dragging.value = false
    settle()
  }
}

let observer: ResizeObserver | null = null

onMounted(() => {
  beginLoad()
  observer = new ResizeObserver(([entry]) => {
    frame.width = entry.contentRect.width
    frame.height = entry.contentRect.height
    // Re-fit before the image is measured; otherwise keep it in the hard bounds.
    apply(
      image.width
        ? clampTranslate({ ...view, scale: clampScale(view.scale, frame, image) }, frame, image)
        : fitView(frame, image),
    )
  })
  if (frameEl.value) observer.observe(frameEl.value)
  // A cached image can finish before the listener is attached, with no `load` to come.
  if (imageEl.value?.complete) onImageLoad()
})

onBeforeUnmount(() => {
  observer?.disconnect()
  clearTimeout(settleTimer)
  clearTimeout(hintTimer)
  clearTimeout(slowTimer)
})

// A new picture resets the view once its natural size arrives via onImageLoad.
watch(
  () => props.src,
  () => {
    image.width = 0
    image.height = 0
    beginLoad()
  },
)

// Exposed for the dev sandbox / tests to observe and drive the transform, and
// for GamePanel to line the guess overlay up with the picture.
defineExpose({ view, reset, contentTop })
</script>

<template>
  <div
    ref="frameEl"
    class="relative h-full w-full touch-none select-none overflow-hidden rounded-lg bg-black/80"
    :class="dragging ? 'cursor-grabbing' : 'cursor-grab'"
    @wheel="onWheel"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
    @dblclick="reset"
  >
    <!-- The wrapper owns the reveal fade so it can't fight the transform transition. -->
    <div
      class="absolute inset-0 transition-opacity duration-300"
      :class="ready ? 'opacity-100' : 'opacity-0'"
    >
      <img
        ref="imageEl"
        :src="props.src"
        :alt="props.alt ?? ''"
        draggable="false"
        class="absolute left-0 top-0 max-w-none origin-top-left"
        :class="{ 'transition-transform duration-200 ease-out': settling }"
        :style="{ transform: `translate(${view.tx}px, ${view.ty}px) scale(${view.scale})` }"
        @load="onImageLoad"
        @error="onImageError"
      />
    </div>

    <div
      v-if="slow || failed"
      class="absolute inset-0 flex flex-col items-center justify-center gap-3 text-center"
    >
      <template v-if="loading">
        <svg class="h-8 w-8 animate-spin text-turn" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="3" opacity="0.25" />
          <path
            d="M21 12a9 9 0 0 0-9-9"
            stroke="currentColor"
            stroke-width="3"
            stroke-linecap="round"
          />
        </svg>
        <p class="text-sm text-white/70">Loading image…</p>
      </template>
      <p v-else class="text-sm text-white/70">Couldn’t load this image.</p>
    </div>

    <!-- Overlays are pinned to the frame's own corners, clear of the picture's controls. -->
    <Transition
      enter-active-class="transition-opacity duration-300"
      leave-active-class="transition-opacity duration-300"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <p
        v-if="showHint"
        class="pointer-events-none absolute bottom-3 left-3 rounded-lg bg-black/60 px-2.5 py-1.5 text-xs text-white/85 ring-1 ring-white/15 backdrop-blur-sm"
      >
        Drag to pan · scroll or pinch to zoom · double-click to reset
      </p>
    </Transition>

    <div
      v-if="ready"
      class="absolute bottom-3 right-3 flex items-center gap-0.5 rounded-lg bg-black/60 p-1 ring-1 ring-white/15 backdrop-blur-sm"
      @pointerdown.stop
      @dblclick.stop
      @wheel.stop
    >
      <span v-if="!fitted" class="px-1.5 font-mono text-xs tabular-nums text-white/70">
        {{ percent }}%
      </span>
      <button
        type="button"
        class="grid h-7 w-7 cursor-pointer place-items-center rounded text-white/80 hover:bg-white/15 hover:text-white disabled:cursor-default disabled:opacity-35 disabled:hover:bg-transparent"
        :disabled="fitted"
        title="Zoom out"
        aria-label="Zoom out"
        @click="zoomBy(1 / ZOOM_STEP)"
      >
        <IconZoomOut class="h-4 w-4" />
      </button>
      <button
        type="button"
        class="grid h-7 w-7 cursor-pointer place-items-center rounded text-white/80 hover:bg-white/15 hover:text-white disabled:cursor-default disabled:opacity-35 disabled:hover:bg-transparent"
        :disabled="maxed"
        title="Zoom in"
        aria-label="Zoom in"
        @click="zoomBy(ZOOM_STEP)"
      >
        <IconZoomIn class="h-4 w-4" />
      </button>
      <button
        type="button"
        class="grid h-7 w-7 cursor-pointer place-items-center rounded text-white/80 hover:bg-white/15 hover:text-white disabled:cursor-default disabled:opacity-35 disabled:hover:bg-transparent"
        :disabled="fitted"
        title="Reset to fit"
        aria-label="Reset to fit"
        @click="reset"
      >
        <IconFit class="h-4 w-4" />
      </button>
    </div>
  </div>
</template>
