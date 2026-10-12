// Running checks and turning results into history entries.

import { api, type LinePayload } from './api'
import type { Session } from './flow'
import { problemsOf } from './flow'
import type { HistoryEntry } from './state'
import type { CheckResponse, DraftLine } from './types'

/** API payload for one problem. Indexes are positions within the problem, so hints
 *  ("between lines 2 and 3") match the numbering the student sees. */
export function payloadFor(drafts: DraftLine[]): LinePayload[] {
  return drafts.map((d, i) => ({ index: i, math: d.math, type: d.type }))
}

/** Lines of one problem, in order. */
export function linesOf(drafts: DraftLine[], problem: number): DraftLine[] {
  return drafts.filter((d) => d.problem === problem)
}

/** Re-number lines 0..n-1 (after merging, deleting or adding lines). */
export function reindex(drafts: DraftLine[]): DraftLine[] {
  return drafts.map((d, i) => ({ ...d, index: i }))
}

export function draftsNeedingAttention(drafts: DraftLine[]): DraftLine[] {
  return drafts.filter((d) => d.type !== 'note' && (!d.math.trim() || !d.confirmed || !!d.error))
}

export async function checkAll(session: Session, acknowledge = false): Promise<Record<number, CheckResponse>> {
  const problems = problemsOf(session.drafts)
  const results = await Promise.all(problems.map((p) => api.check(payloadFor(linesOf(session.drafts, p)), acknowledge)))
  const out: Record<number, CheckResponse> = {}
  problems.forEach((p, i) => {
    out[p] = results[i]
  })
  return out
}

export function historyId(session: Session, problem: number): string {
  return session.mode === 'page' ? `${session.id}-${problem}` : session.id
}

export function buildHistoryEntry(session: Session, problem: number, result: CheckResponse, lines: DraftLine[], prev?: HistoryEntry): HistoryEntry {
  const now = Date.now()
  const byIndex = new Map(result.lines.map((l) => [l.index, l]))
  const errors = result.lines
    .filter((l) => l.status === 'error')
    .map((l) => ({ type: l.error_type ?? 'general', subtype: l.subtype, line: l.index }))
  return {
    id: historyId(session, problem),
    createdAt: prev?.createdAt ?? session.createdAt ?? now,
    updatedAt: now,
    source: session.source,
    title: session.title,
    topic: result.topic || 'none',
    lines: lines.map((d, i) => {
      const r = byIndex.get(i)
      return { index: i, math: d.math, latex: d.latex, type: d.type, status: r?.status, tier: r?.tier, error_type: r?.error_type }
    }),
    firstError: result.first_error,
    // Keep the original mistakes even after the student fixes them.
    errors: prev && prev.errors.length ? prev.errors : errors,
    allCorrect: result.all_correct,
    fixed: prev?.fixed ?? false,
    fixedAt: prev?.fixedAt,
    hintsUsed: Math.max(prev?.hintsUsed ?? 0, session.hintsShown[problem] ?? 0),
    photoId: prev?.photoId,
  }
}
