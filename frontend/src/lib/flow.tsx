// The check in progress: photo -> confirm -> result -> fix.
// Kept in sessionStorage so a refresh doesn't lose the student's work.

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { CheckResponse, DraftLine, ReadLine, ReadResponse } from './types'
import { uid } from './state'

export interface Session {
  id: string
  source: 'photo' | 'sample' | 'typed' | 'practice'
  title?: string
  photo: { src: string; width: number; height: number } | null
  mode: 'problem' | 'page'
  readSource?: ReadResponse['source']
  warnings: string[]
  drafts: DraftLine[]
  // Results per problem (whole-page mode can hold several).
  results: Record<number, CheckResponse>
  checkedLines: Record<number, DraftLine[]>
  hintsShown: Record<number, number>
  logged: Record<number, boolean>
  fixed: Record<number, boolean>
  savePhoto: boolean
  createdAt: number
  editedKeys?: string[]
}

const KEY = 'wdigw:session'

function load(): Session | null {
  try {
    const s = sessionStorage.getItem(KEY)
    if (!s) return null
    const v = JSON.parse(s)
    if (!v || typeof v.id !== 'string' || !Array.isArray(v.drafts)) return null
    return v as Session
  } catch {
    return null
  }
}

function persist(s: Session | null) {
  try {
    if (!s) sessionStorage.removeItem(KEY)
    else sessionStorage.setItem(KEY, JSON.stringify(s))
  } catch {
    // Too big (a large photo): keep everything but the photo.
    try {
      if (s) sessionStorage.setItem(KEY, JSON.stringify({ ...s, photo: s.photo?.src.startsWith('data:') ? null : s.photo }))
    } catch {
      /* give up on persistence */
    }
  }
}

export function draftFromRead(l: ReadLine): DraftLine {
  return {
    key: uid(),
    index: l.index,
    math: l.math ?? '',
    latex: l.latex ?? '',
    type: l.type ?? 'equation',
    confidence: l.confidence ?? 'low',
    alternatives: l.alternatives ?? [],
    // Confident lines are confirmed already; uncertain ones need a tap.
    confirmed: l.confidence === 'high' && !!l.math && !l.parse_error,
    crop: l.crop,
    box: l.box,
    quad: l.quad,
    problem: l.problem ?? 0,
    original: l.math ?? '',
    error: l.parse_error ?? null,
    lookalike: l.lookalike,
  }
}

export function blankDraft(index: number, math = '', problem = 0): DraftLine {
  return { key: uid(), index, math, latex: '', type: 'equation', confidence: 'high', alternatives: [],
    confirmed: !!math, problem, original: math, error: null }
}

export function newSession(partial: Partial<Session> & Pick<Session, 'source'>): Session {
  return {
    id: uid(),
    photo: null,
    mode: 'problem',
    warnings: [],
    drafts: [],
    results: {},
    checkedLines: {},
    hintsShown: {},
    logged: {},
    fixed: {},
    savePhoto: false,
    createdAt: Date.now(),
    ...partial,
  }
}

interface FlowValue {
  session: Session | null
  start: (s: Session) => void
  update: (fn: (s: Session) => Session) => void
  clear: () => void
  photoBlob: Blob | null
  setPhotoBlob: (b: Blob | null) => void
}

const FlowContext = createContext<FlowValue | null>(null)

export function FlowProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(load)
  const [photoBlob, setPhotoBlob] = useState<Blob | null>(null)

  useEffect(() => {
    persist(session)
  }, [session])

  const start = useCallback((s: Session) => setSession(s), [])
  const update = useCallback((fn: (s: Session) => Session) => setSession((s) => (s ? fn(s) : s)), [])
  const clear = useCallback(() => {
    setSession(null)
    setPhotoBlob(null)
  }, [])

  const value = useMemo(() => ({ session, start, update, clear, photoBlob, setPhotoBlob }),
    [session, start, update, clear, photoBlob])
  return <FlowContext.Provider value={value}>{children}</FlowContext.Provider>
}

export function useFlow(): FlowValue {
  const v = useContext(FlowContext)
  if (!v) throw new Error('useFlow must be used inside FlowProvider')
  return v
}

/** Group drafts by problem (whole-page mode). */
export function problemsOf(drafts: DraftLine[]): number[] {
  return [...new Set(drafts.map((d) => d.problem))].sort((a, b) => a - b)
}
