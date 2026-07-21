import { describe, expect, it } from 'vitest'

import {
  clampScale,
  clampTranslate,
  fitScale,
  fitView,
  isFitted,
  isMaxZoomed,
  panBy,
  pictureTop,
  zoomPercent,
  zoomToPoint,
  type View,
} from './viewerGeometry'

const frame = { width: 100, height: 100 }

describe('fitScale', () => {
  it('contains the image: the limiting dimension fills the frame', () => {
    expect(fitScale(frame, { width: 200, height: 100 })).toBe(0.5) // width-limited
    expect(fitScale(frame, { width: 50, height: 200 })).toBe(0.5) // height-limited
  })

  it('falls back to 1 for an unmeasured image', () => {
    expect(fitScale(frame, { width: 0, height: 0 })).toBe(1)
  })
})

describe('clampScale', () => {
  it('clamps to [fit, fit·8]', () => {
    const image = { width: 100, height: 100 } // fit = 1
    expect(clampScale(0.2, frame, image)).toBe(1)
    expect(clampScale(100, frame, image)).toBe(8)
    expect(clampScale(3, frame, image)).toBe(3)
  })
})

describe('clampTranslate', () => {
  it('centers an axis where the image is smaller than the frame', () => {
    const image = { width: 100, height: 100 }
    const view: View = { scale: 0.5, tx: 999, ty: -999 } // displayed 50×50
    expect(clampTranslate(view, frame, image)).toEqual({ scale: 0.5, tx: 25, ty: 25 })
  })

  it('keeps a covering image gap-free (edges stay outside the frame)', () => {
    const image = { width: 100, height: 100 }
    const view: View = { scale: 2, tx: 50, ty: -500 } // displayed 200×200
    // tx clamps to 0 (left edge can't move right of the frame edge),
    // ty clamps to -100 (bottom edge can't move above the frame edge).
    expect(clampTranslate(view, frame, image)).toEqual({ scale: 2, tx: 0, ty: -100 })
  })
})

describe('clampTranslate — elastic (give > 0)', () => {
  const image = { width: 100, height: 100 }

  it('lets a covering image overshoot the edge, damped and capped by give', () => {
    const view: View = { scale: 2, tx: 50, ty: 0 } // displayed 200; hi edge is 0, over by 50
    const { tx } = clampTranslate(view, frame, image, 100)
    // rubber(50, 100) = 100·(1 − 1/1.5) = 33.33 → less than the raw 50, under give.
    expect(tx).toBeCloseTo(33.33, 1)
    expect(tx).toBeLessThan(50)
    expect(tx).toBeLessThan(100)
  })

  it('lets a centered (fit) image be nudged instead of locking solid', () => {
    const view: View = { scale: 0.5, tx: 125, ty: 25 } // center is 25; over by 100
    const { tx } = clampTranslate(view, frame, image, 100)
    expect(tx).toBeCloseTo(75, 5) // 25 + rubber(100,100)=50
  })

  it('is a hard stop again with give = 0', () => {
    const view: View = { scale: 2, tx: 50, ty: 0 }
    expect(clampTranslate(view, frame, image, 0).tx).toBe(0)
  })
})

describe('fitView', () => {
  it('is the minimum scale, centered', () => {
    expect(fitView(frame, { width: 200, height: 100 })).toEqual({ scale: 0.5, tx: 0, ty: 25 })
  })
})

describe('range predicates', () => {
  const image = { width: 200, height: 200 } // fit = 0.5, max = 4

  it('reports a fitted view, including one nudged below fit by rounding', () => {
    expect(isFitted({ scale: 0.5, tx: 0, ty: 0 }, frame, image)).toBe(true)
    expect(isFitted({ scale: 0.5000001, tx: 0, ty: 0 }, frame, image)).toBe(true)
    expect(isFitted({ scale: 0.6, tx: 0, ty: 0 }, frame, image)).toBe(false)
  })

  it('reports a maxed-out view', () => {
    expect(isMaxZoomed({ scale: 4, tx: 0, ty: 0 }, frame, image)).toBe(true)
    expect(isMaxZoomed({ scale: 3.9999999, tx: 0, ty: 0 }, frame, image)).toBe(true)
    expect(isMaxZoomed({ scale: 3, tx: 0, ty: 0 }, frame, image)).toBe(false)
  })
})

describe('zoomPercent', () => {
  it('counts from fit-to-frame, not from the image’s natural size', () => {
    const image = { width: 200, height: 200 } // fit = 0.5
    expect(zoomPercent({ scale: 0.5, tx: 0, ty: 0 }, frame, image)).toBe(100)
    expect(zoomPercent({ scale: 1, tx: 0, ty: 0 }, frame, image)).toBe(200)
    expect(zoomPercent({ scale: 4, tx: 0, ty: 0 }, frame, image)).toBe(800)
  })
})

describe('zoomToPoint', () => {
  it('keeps the pixel under the pivot fixed', () => {
    const image = { width: 100, height: 100 }
    const start: View = { scale: 1, tx: 0, ty: 0 }
    const pivot = { x: 50, y: 50 }
    const pixelBefore = {
      x: (pivot.x - start.tx) / start.scale,
      y: (pivot.y - start.ty) / start.scale,
    }

    const next = zoomToPoint(start, 2, pivot, frame, image)
    const pixelAfter = { x: (pivot.x - next.tx) / next.scale, y: (pivot.y - next.ty) / next.scale }

    expect(next.scale).toBe(2)
    expect(pixelAfter).toEqual(pixelBefore)
  })

  it('clamps the scale before positioning', () => {
    const image = { width: 100, height: 100 }
    const next = zoomToPoint({ scale: 1, tx: 0, ty: 0 }, 999, { x: 50, y: 50 }, frame, image)
    expect(next.scale).toBe(8)
  })
})

describe('pictureTop', () => {
  it('measures the letterbox band of a fitted image', () => {
    const wide = fitView(frame, { width: 200, height: 100 }) // displayed 100×50
    expect(pictureTop(wide)).toBe(25)
    const tall = fitView(frame, { width: 50, height: 200 }) // fills the height, no band
    expect(pictureTop(tall)).toBe(0)
  })

  it('reports no band once the picture runs off the top', () => {
    expect(pictureTop({ scale: 2, tx: 0, ty: -50 })).toBe(0)
  })
})

describe('panBy', () => {
  it('applies a delta and re-clamps into frame', () => {
    const image = { width: 100, height: 100 }
    const zoomed: View = { scale: 2, tx: -50, ty: -50 } // displayed 200×200, centered-ish
    expect(panBy(zoomed, 30, 30, frame, image)).toEqual({ scale: 2, tx: -20, ty: -20 })
    // Dragging past the edge clamps to 0 (can't expose a gap).
    expect(panBy(zoomed, 999, 0, frame, image)).toEqual({ scale: 2, tx: 0, ty: -50 })
  })
})
