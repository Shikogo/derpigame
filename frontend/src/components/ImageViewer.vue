<script setup lang="ts">
/**
 * Bounded pan/zoom image frame. Drag to pan, wheel / trackpad-pinch / two-finger
 * pinch to zoom toward the pointer, double-click to reset to fit. All the math is
 * in `@/lib/viewerGeometry`; this component owns the reactive view and turns
 * pointer/wheel events into geometry calls.
 *
 * Edges are elastic: a drag can pull the image past the frame with rubber-band
 * resistance, then springs back to the hard bound on release.
 */
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

import {
  clampScale,
  clampTranslate,
  fitView,
  panBy,
  zoomToPoint,
  type Size,
  type View,
} from '@/lib/viewerGeometry'

const props = defineProps<{ src: string; alt?: string }>()

const frameEl = ref<HTMLElement | null>(null)
const frame = reactive<Size>({ width: 0, height: 0 })
const image = reactive<Size>({ width: 0, height: 0 })
const view = reactive<View>({ scale: 1, tx: 0, ty: 0 })
const settling = ref(false) // animate transform back to bounds after a release

const pointers = new Map<number, { x: number; y: number }>()
let pinchDist = 0
let settleTimer: ReturnType<typeof setTimeout> | undefined

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
  animateTo(fitView(frame, image))
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

function onImageLoad(e: Event): void {
  const img = e.target as HTMLImageElement
  image.width = img.naturalWidth
  image.height = img.naturalHeight
  apply(fitView(frame, image))
}

function onWheel(e: WheelEvent): void {
  e.preventDefault()
  stopSettling()
  const factor = Math.exp(-e.deltaY * 0.0015)
  apply(zoomToPoint(view, view.scale * factor, localPoint(e.clientX, e.clientY), frame, image))
}

function onPointerDown(e: PointerEvent): void {
  ;(e.target as Element).setPointerCapture(e.pointerId)
  stopSettling()
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
  pinchDist = 0
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
  if (pointers.size === 0) settle()
}

let observer: ResizeObserver | null = null

onMounted(() => {
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
})

onBeforeUnmount(() => {
  observer?.disconnect()
  clearTimeout(settleTimer)
})

// A new picture resets the view once its natural size arrives via onImageLoad.
watch(
  () => props.src,
  () => {
    image.width = 0
    image.height = 0
  },
)

// Exposed for the dev sandbox / tests to observe and drive the transform.
defineExpose({ view, reset })
</script>

<template>
  <div
    ref="frameEl"
    class="relative h-full w-full touch-none select-none overflow-hidden rounded-lg bg-black/80"
    @wheel="onWheel"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
    @dblclick="reset"
  >
    <img
      :src="props.src"
      :alt="props.alt ?? ''"
      draggable="false"
      class="absolute left-0 top-0 max-w-none origin-top-left"
      :class="{ 'transition-transform duration-200 ease-out': settling }"
      :style="{ transform: `translate(${view.tx}px, ${view.ty}px) scale(${view.scale})` }"
      @load="onImageLoad"
    />
  </div>
</template>
