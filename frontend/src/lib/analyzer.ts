// Guided-camera frame checks, in plain JavaScript pixel math (spec: "Guided
// camera"). About 6 times a second a ~320 px copy of the video frame is
// analysed. One message shows at a time, most important problem first.

export type Issue = 'dark' | 'glare' | 'small' | 'cutoff' | 'offcenter' | 'moving' | 'blurry' | 'nowriting'

export const ISSUE_ORDER: Issue[] = ['dark', 'glare', 'small', 'cutoff', 'offcenter', 'moving', 'blurry', 'nowriting']

export const MESSAGES: Record<Issue, string> = {
  dark: 'Find more light',
  glare: 'Glare detected. Tilt your phone slightly.',
  small: 'Move closer',
  cutoff: 'Move back a little',
  offcenter: 'Center the page',
  moving: 'Hold still…',
  blurry: 'Hold steady',
  nowriting: "Can't find any work. Is the page in view?",
}

// Starting points; tune on a real phone with the on-screen metrics (Settings → camera metrics).
export const THRESHOLDS = {
  minBrightness: 60,      // average brightness 0-255 when no paper is found
  minPaperBrightness: 105, // brightness of the paper itself
  maxGlare: 0.05,         // share of paper pixels above 250
  minPaperArea: 0.2,      // paper region vs frame
  maxOffCenter: 0.22,     // paper-centre distance from frame centre (fraction of frame)
  maxMotion: 9,           // mean absolute difference between frames
  minSharpness: 70,       // RMS Laplacian on stroke edges
  minInk: 0.0015,         // share of dark pixels inside the paper
  edgeBand: 0.03,         // work this close to the frame edge counts as cut off
}

export interface FrameMetrics {
  brightness: number
  paperBrightness: number
  glare: number
  paperArea: number
  paperBox: { x0: number; y0: number; x1: number; y1: number } | null
  offCenter: number
  motion: number
  sharpness: number
  ink: number
  inkAtEdge: number
}

export function toGray(rgba: Uint8ClampedArray, w: number, h: number): Uint8Array {
  const g = new Uint8Array(w * h)
  for (let i = 0, j = 0; i < g.length; i++, j += 4) {
    g[i] = (rgba[j] * 77 + rgba[j + 1] * 150 + rgba[j + 2] * 29) >> 8
  }
  return g
}

function otsu(gray: Uint8Array): number {
  const hist = new Array(256).fill(0)
  for (let i = 0; i < gray.length; i++) hist[gray[i]]++
  const total = gray.length
  let sum = 0
  for (let t = 0; t < 256; t++) sum += t * hist[t]
  let sumB = 0
  let wB = 0
  let best = 0
  let threshold = 127
  for (let t = 0; t < 256; t++) {
    wB += hist[t]
    if (!wB) continue
    const wF = total - wB
    if (!wF) break
    sumB += t * hist[t]
    const mB = sumB / wB
    const mF = (sum - sumB) / wF
    const between = wB * wF * (mB - mF) * (mB - mF)
    if (between > best) {
      best = between
      threshold = t
    }
  }
  return threshold
}

/** Largest connected bright region (4-connectivity) - the paper. */
function largestBrightRegion(gray: Uint8Array, w: number, h: number, threshold: number) {
  const labels = new Int32Array(w * h)
  const stack = new Int32Array(w * h)
  let best = { count: 0, label: 0, x0: 0, y0: 0, x1: 0, y1: 0 }
  let label = 0
  for (let start = 0; start < gray.length; start++) {
    if (labels[start] || gray[start] <= threshold) continue
    label++
    let sp = 0
    stack[sp++] = start
    labels[start] = label
    let count = 0
    let x0 = w, y0 = h, x1 = 0, y1 = 0
    while (sp) {
      const p = stack[--sp]
      count++
      const x = p % w
      const y = (p - x) / w
      if (x < x0) x0 = x
      if (x > x1) x1 = x
      if (y < y0) y0 = y
      if (y > y1) y1 = y
      if (x > 0) { const q = p - 1; if (!labels[q] && gray[q] > threshold) { labels[q] = label; stack[sp++] = q } }
      if (x < w - 1) { const q = p + 1; if (!labels[q] && gray[q] > threshold) { labels[q] = label; stack[sp++] = q } }
      if (y > 0) { const q = p - w; if (!labels[q] && gray[q] > threshold) { labels[q] = label; stack[sp++] = q } }
      if (y < h - 1) { const q = p + w; if (!labels[q] && gray[q] > threshold) { labels[q] = label; stack[sp++] = q } }
    }
    if (count > best.count) best = { count, label, x0, y0, x1, y1 }
  }
  return { ...best, labels }
}

export function analyzeFrame(gray: Uint8Array, w: number, h: number, prev: Uint8Array | null): FrameMetrics {
  const n = w * h
  let sum = 0
  for (let i = 0; i < n; i++) sum += gray[i]
  const brightness = sum / n

  let motion = 0
  if (prev && prev.length === n) {
    let d = 0
    for (let i = 0; i < n; i += 2) d += Math.abs(gray[i] - prev[i])
    motion = d / (n / 2)
  }

  const t = Math.max(otsu(gray), 90)
  const region = largestBrightRegion(gray, w, h, t)
  const paperArea = region.count / n
  if (region.count < n * 0.02) {
    return { brightness, paperBrightness: 0, glare: 0, paperArea, paperBox: null, offCenter: 1, motion, sharpness: 0, ink: 0, inkAtEdge: 0 }
  }
  const { x0, y0, x1, y1, labels, label } = region

  // Paper statistics inside its bounding box (ink pixels are holes in the region, so use the box).
  // Per-row extent of the paper, so desk corners of a tilted page aren't counted as ink.
  let paperSum = 0
  let paperCount = 0
  let glareCount = 0
  const hist = new Uint32Array(256)
  const rowMin = new Int32Array(h).fill(-1)
  const rowMax = new Int32Array(h).fill(-1)
  for (let y = y0; y <= y1; y++) {
    for (let x = x0; x <= x1; x++) {
      const p = y * w + x
      if (labels[p] === label) {
        paperSum += gray[p]
        paperCount++
        hist[gray[p]]++
        if (gray[p] > 250) glareCount++
        if (rowMin[y] < 0) rowMin[y] = x
        rowMax[y] = x
      }
    }
  }
  const paperMean = paperCount ? paperSum / paperCount : 0
  // Glare is a hotspot that stands out from the paper. Evenly bright (even
  // saturated) paper still shows the writing, so it doesn't count.
  let acc = 0
  let paperMedian = 255
  for (let v = 0; v < 256; v++) {
    acc += hist[v]
    if (acc >= paperCount / 2) {
      paperMedian = v
      break
    }
  }
  const glare = paperCount && paperMedian < 228 ? glareCount / paperCount : 0

  // Ink: clearly darker than the paper, inside the paper box.
  const inkLevel = paperMean - 45
  const bandX = Math.max(2, Math.round(w * THRESHOLDS.edgeBand))
  const bandY = Math.max(2, Math.round(h * THRESHOLDS.edgeBand))
  let ink = 0
  let inkEdge = 0
  let boxCount = 0
  // Sharpness: RMS of the 4-neighbour Laplacian on stroke edges. Measuring only
  // at edges keeps the score independent of how much writing is on the page.
  let lapSq = 0
  let lapN = 0
  for (let y = Math.max(1, y0); y <= Math.min(h - 2, y1); y++) {
    if (rowMin[y] < 0) continue
    for (let x = Math.max(1, rowMin[y]); x <= Math.min(w - 2, rowMax[y]); x++) {
      const p = y * w + x
      boxCount++
      const v = gray[p]
      if (v < inkLevel) {
        ink++
        if (x < bandX || x >= w - bandX || y < bandY || y >= h - bandY) inkEdge++
      }
      const l = gray[p - 1], r = gray[p + 1], u = gray[p - w], d = gray[p + w]
      const hi = Math.max(v, l, r, u, d)
      const lo = Math.min(v, l, r, u, d)
      if (hi - lo > 40) {
        const lap = 4 * v - l - r - u - d
        lapSq += lap * lap
        lapN++
      }
    }
  }
  const sharpness = lapN ? Math.sqrt(lapSq / lapN) : 0
  const cx = (x0 + x1) / 2 / w - 0.5
  const cy = (y0 + y1) / 2 / h - 0.5
  return {
    brightness,
    paperBrightness: paperMean,
    glare,
    paperArea,
    paperBox: { x0: x0 / w, y0: y0 / h, x1: x1 / w, y1: y1 / h },
    offCenter: Math.sqrt(cx * cx + cy * cy),
    motion,
    sharpness,
    ink: boxCount ? ink / boxCount : 0,
    inkAtEdge: ink ? inkEdge / ink : 0,
  }
}

/** The most important problem with this frame, or null if it's good. */
export function findIssue(m: FrameMetrics, th = THRESHOLDS): Issue | null {
  if (m.paperBox ? m.paperBrightness < th.minPaperBrightness : m.brightness < th.minBrightness) return 'dark'
  if (m.paperBox && m.glare > th.maxGlare) return 'glare'
  if (!m.paperBox || m.paperArea < th.minPaperArea) return 'small'
  if (m.inkAtEdge > 0.04) return 'cutoff'
  if (m.offCenter > th.maxOffCenter) return 'offcenter'
  if (m.motion > th.maxMotion) return 'moving'
  // Sharpness can only be judged where there's writing.
  if (m.ink < th.minInk) return 'nowriting'
  if (m.sharpness < th.minSharpness) return 'blurry'
  return null
}

/**
 * No-flicker message logic and auto-capture counter.
 * The shown message changes only after the same issue appears 3 frames in a
 * row; capture fires after every check passes for 6 frames in a row.
 */
export class Guide {
  shown: Issue | null = 'small'
  private candidate: Issue | null = null
  private candidateRun = 0
  goodRun = 0
  readonly stableFrames: number
  readonly captureFrames: number

  constructor(stableFrames = 3, captureFrames = 6) {
    this.stableFrames = stableFrames
    this.captureFrames = captureFrames
  }

  push(issue: Issue | null): { message: Issue | null; progress: number; capture: boolean } {
    if (issue === this.candidate) this.candidateRun++
    else {
      this.candidate = issue
      this.candidateRun = 1
    }
    if (this.candidateRun >= this.stableFrames) this.shown = this.candidate
    this.goodRun = issue === null ? this.goodRun + 1 : 0
    const capture = this.goodRun >= this.captureFrames
    return { message: this.shown, progress: Math.min(1, this.goodRun / this.captureFrames), capture }
  }

  reset() {
    this.shown = 'small'
    this.candidate = null
    this.candidateRun = 0
    this.goodRun = 0
  }
}
