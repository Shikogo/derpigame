/**
 * Pure pan/zoom math for `ImageViewer` — no Vue, no DOM, so it's unit-testable
 * in isolation. The component owns the reactive state and event plumbing; every
 * geometric decision (fit, clamp, zoom-to-point, pan) lives here.
 *
 * Coordinate model: the image layer is `translate(tx, ty) scale(s)` with a
 * top-left transform origin, so it occupies `[tx, tx + w·s] × [ty, ty + h·s]`
 * in frame space.
 */

export interface Size {
  width: number
  height: number
}

export interface Point {
  x: number
  y: number
}

export interface View {
  scale: number
  tx: number
  ty: number
}

/** How far past fit-to-frame a user may zoom in. */
export const MAX_ZOOM_FACTOR = 8

/** Multiplier for one press of a zoom button. */
export const ZOOM_STEP = 1.6

// Scales are floating-point, so the range ends need a little slack to test against.
const SLACK = 1.001

/** Scale at which the whole image fits inside the frame (contain). */
export function fitScale(frame: Size, image: Size): number {
  if (image.width <= 0 || image.height <= 0) return 1
  return Math.min(frame.width / image.width, frame.height / image.height)
}

/** The allowed scale range: fit-to-frame up to `factor`× that. */
export function scaleBounds(frame: Size, image: Size, factor = MAX_ZOOM_FACTOR) {
  const min = fitScale(frame, image)
  return { min, max: min * factor }
}

/** Clamp a desired scale into `[fit, fit·factor]`. */
export function clampScale(
  scale: number,
  frame: Size,
  image: Size,
  factor = MAX_ZOOM_FACTOR,
): number {
  const { min, max } = scaleBounds(frame, image, factor)
  return Math.min(Math.max(scale, min), max)
}

/**
 * Clamp translation into frame. By default a hard stop: the image never reveals
 * a gap when it covers the frame, and stays centered along any axis where it's
 * smaller. With `give > 0` the bounds turn elastic — a drag may pull the image
 * past an edge with rubber-band resistance (never more than ~`give` px) for a
 * softer feel; release settles it back with `give = 0`.
 */
export function clampTranslate(view: View, frame: Size, image: Size, give = 0): View {
  return {
    scale: view.scale,
    tx: clampAxis(view.tx, image.width * view.scale, frame.width, give),
    ty: clampAxis(view.ty, image.height * view.scale, frame.height, give),
  }
}

function clampAxis(t: number, displayed: number, frame: number, give: number): number {
  // Resting range for this axis: a single centered point when the image is
  // smaller than the frame, else the covering span [frame - displayed, 0].
  const lo = displayed <= frame ? (frame - displayed) / 2 : frame - displayed
  const hi = displayed <= frame ? lo : 0
  if (t < lo) return lo - rubber(lo - t, give)
  if (t > hi) return hi + rubber(t - hi, give)
  return t
}

// Rubber-band resistance: 0 for a hard stop (`give = 0`), otherwise an overshoot
// that grows sub-linearly and asymptotically caps at `give` px (iOS-style).
function rubber(overshoot: number, give: number): number {
  if (give <= 0) return 0
  return give * (1 - 1 / (overshoot / give + 1))
}

/** Whether the view is already fitted, i.e. resetting or zooming out is a no-op. */
export function isFitted(view: View, frame: Size, image: Size): boolean {
  return view.scale <= fitScale(frame, image) * SLACK
}

/** Whether the view is zoomed all the way in, i.e. zooming in further is a no-op. */
export function isMaxZoomed(
  view: View,
  frame: Size,
  image: Size,
  factor = MAX_ZOOM_FACTOR,
): boolean {
  return view.scale >= scaleBounds(frame, image, factor).max / SLACK
}

/** Zoom level for display: 100% is the whole image in frame, 800% the max. */
export function zoomPercent(view: View, frame: Size, image: Size): number {
  return Math.round((view.scale / fitScale(frame, image)) * 100)
}

/**
 * Top edge of the picture in frame space, i.e. the height of the letterbox band
 * above it — how much room anything pinned to the picture has to sit in. Zero
 * once the picture reaches or passes the frame's top edge.
 */
export function pictureTop(view: View): number {
  return Math.max(view.ty, 0)
}

/** Fit-to-frame view: minimum scale, centered. */
export function fitView(frame: Size, image: Size): View {
  return clampTranslate({ scale: fitScale(frame, image), tx: 0, ty: 0 }, frame, image)
}

/**
 * Zoom to `nextScale` (clamped) while keeping the frame point `pivot` over the
 * same image pixel — the point under the cursor / pinch-midpoint stays put.
 */
export function zoomToPoint(
  view: View,
  nextScale: number,
  pivot: Point,
  frame: Size,
  image: Size,
  give = 0,
): View {
  const scale = clampScale(nextScale, frame, image)
  const ratio = scale / view.scale
  return clampTranslate(
    {
      scale,
      tx: pivot.x - (pivot.x - view.tx) * ratio,
      ty: pivot.y - (pivot.y - view.ty) * ratio,
    },
    frame,
    image,
    give,
  )
}

/** Drag the image by a delta, clamped (optionally elastic) back into frame. */
export function panBy(
  view: View,
  dx: number,
  dy: number,
  frame: Size,
  image: Size,
  give = 0,
): View {
  return clampTranslate(
    { scale: view.scale, tx: view.tx + dx, ty: view.ty + dy },
    frame,
    image,
    give,
  )
}
