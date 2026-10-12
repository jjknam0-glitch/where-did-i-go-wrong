// Mistake profile statistics, streaks and plan rules (pure functions).

import type { AppState, HistoryEntry } from './state'
import type { Plan } from './types'

const DAY = 86_400_000

export const ERROR_LABELS: Record<string, { name: string; plural: string; skill: string }> = {
  sign_error: { name: 'sign error', plural: 'sign errors', skill: 'sign_error' },
  one_side_only: { name: 'one-side-only step', plural: 'one-side-only steps', skill: 'one_side_only' },
  distribution_error: { name: 'distribution error', plural: 'distribution errors', skill: 'distribution_error' },
  arithmetic_slip: { name: 'arithmetic slip', plural: 'arithmetic slips', skill: 'arithmetic_slip' },
  exponent_rule: { name: 'exponent-rule mistake', plural: 'exponent-rule mistakes', skill: 'exponent_rule' },
  inequality_flip: { name: 'missed inequality flip', plural: 'missed inequality flips', skill: 'inequality_flip' },
  derivative_rule: { name: 'derivative-rule mistake', plural: 'derivative-rule mistakes', skill: 'derivative_rule' },
  antiderivative_error: { name: 'antiderivative mistake', plural: 'antiderivative mistakes', skill: 'antiderivative_error' },
  lost_solution: { name: 'lost solution', plural: 'lost solutions', skill: 'lost_solution' },
  extra_solution: { name: 'extra solution', plural: 'extra solutions', skill: 'extra_solution' },
  general: { name: 'changed step', plural: 'changed steps', skill: 'general' },
}

export const TOPIC_LABELS: Record<string, string> = {
  linear: 'Linear equations',
  quadratics: 'Quadratics',
  equations: 'Equations',
  simplifying: 'Simplifying',
  factoring: 'Factoring',
  inequalities: 'Inequalities',
  systems: 'Systems',
  exponentials: 'Exponentials & logs',
  trig: 'Trig identities',
  derivatives: 'Derivatives',
  integrals: 'Integrals',
  limits: 'Limits',
  none: 'Other',
}

export const ADVANCED_TOPICS = new Set(['derivatives', 'integrals', 'limits'])
export const UNITS: { id: string; label: string; topics: string[] }[] = [
  { id: 'algebra', label: 'Algebra', topics: ['linear', 'quadratics', 'equations', 'simplifying', 'factoring', 'inequalities', 'systems', 'exponentials', 'trig'] },
  { id: 'calculus', label: 'Calculus', topics: ['derivatives', 'integrals', 'limits'] },
  { id: 'all', label: 'Everything', topics: [] },
]

export function errorLabel(type: string | null | undefined, plural = false): string {
  const l = ERROR_LABELS[type ?? ''] ?? ERROR_LABELS.general
  return plural ? l.plural : l.name
}

export function topicLabel(topic: string | null | undefined): string {
  return TOPIC_LABELS[topic ?? ''] ?? 'Math'
}

export function ordinal(n: number): string {
  const s = ['th', 'st', 'nd', 'rd']
  const v = n % 100
  return n + (s[(v - 20) % 10] || s[v] || s[0])
}

// ----- plans -----

export const FREE_CHECKS_PER_DAY = 5
export const FREE_HISTORY_DAYS = 7

export type Feature = 'all_hints' | 'advanced' | 'full_history' | 'practice' | 'page_mode' | 'test_prep' | 'sharing'

export function hasFeature(plan: Plan, _feature: Feature): boolean {
  return plan === 'plus' || plan === 'family'
}

export function startOfDay(t: number): number {
  const d = new Date(t)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

export function checksToday(state: Pick<AppState, 'checkLog'>, now = Date.now()): number {
  const start = startOfDay(now)
  return state.checkLog.filter((t) => t >= start && t <= now + 60_000).length
}

export function checksLeftToday(state: Pick<AppState, 'checkLog' | 'plan'>, now = Date.now()): number {
  if (hasFeature(state.plan, 'full_history')) return Infinity
  return Math.max(0, FREE_CHECKS_PER_DAY - checksToday(state, now))
}

/** History the plan can see: the last 7 days on Free, everything on Plus. */
export function visibleHistory(state: Pick<AppState, 'history' | 'plan'>, now = Date.now()): HistoryEntry[] {
  if (hasFeature(state.plan, 'full_history')) return state.history
  return state.history.filter((h) => now - h.createdAt <= FREE_HISTORY_DAYS * DAY)
}

// ----- statistics -----

export interface CountRow {
  key: string
  count: number
  pct: number
}

export interface MistakeStats {
  problems: number
  withMistakes: number
  mistakes: number
  fixed: number
  allCorrect: number
  byType: CountRow[]
  byTopic: CountRow[]
}

export function inRange(entries: HistoryEntry[], days: number | null, now = Date.now()): HistoryEntry[] {
  if (days === null) return entries
  return entries.filter((h) => now - h.createdAt <= days * DAY)
}

function rows(counts: Map<string, number>, total: number): CountRow[] {
  return [...counts.entries()]
    .map(([key, count]) => ({ key, count, pct: total ? Math.round((count / total) * 100) : 0 }))
    .sort((a, b) => b.count - a.count || a.key.localeCompare(b.key))
}

export function mistakeStats(entries: HistoryEntry[]): MistakeStats {
  const byType = new Map<string, number>()
  const byTopic = new Map<string, number>()
  let mistakes = 0
  let withMistakes = 0
  let fixed = 0
  let allCorrect = 0
  for (const h of entries) {
    if (h.allCorrect) allCorrect++
    if (h.errors.length) {
      withMistakes++
      if (h.fixed) fixed++
    }
    for (const e of h.errors.slice(0, 1)) {
      mistakes++
      byType.set(e.type, (byType.get(e.type) ?? 0) + 1)
      byTopic.set(h.topic, (byTopic.get(h.topic) ?? 0) + 1)
    }
  }
  return { problems: entries.length, withMistakes, mistakes, fixed, allCorrect,
    byType: rows(byType, mistakes), byTopic: rows(byTopic, mistakes) }
}

/** How many of this kind of mistake in the last 7 days (including ones just logged). */
export function countThisWeek(entries: HistoryEntry[], type: string, now = Date.now()): number {
  return inRange(entries, 7, now).filter((h) => h.errors[0]?.type === type).length
}

export function patternMessage(entries: HistoryEntry[], type: string, now = Date.now()): string {
  const n = countThisWeek(entries, type, now)
  if (n <= 1) return `Your first ${errorLabel(type)} this week — good to catch it early.`
  return `This is your ${ordinal(n)} ${errorLabel(type)} this week.`
}

/** Consecutive days (ending today or yesterday) with at least one check. */
export function dayStreak(entries: HistoryEntry[], now = Date.now()): number {
  const days = new Set(entries.map((h) => startOfDay(h.createdAt)))
  let day = startOfDay(now)
  if (!days.has(day)) day -= DAY
  let streak = 0
  while (days.has(day)) {
    streak++
    day = startOfDay(day - DAY / 2)
  }
  return streak
}

/** Most recent problems in a row without this kind of mistake. */
export function cleanRun(entries: HistoryEntry[], type: string): number {
  let n = 0
  for (const h of entries) {
    if (h.errors[0]?.type === type) break
    n++
  }
  return n
}

/** Most recent mistakes in a row that the student fixed themselves. */
export function fixStreak(entries: HistoryEntry[]): number {
  let n = 0
  for (const h of entries) {
    if (!h.errors.length) continue
    if (!h.fixed) break
    n++
  }
  return n
}

export function weakestSkill(entries: HistoryEntry[], topics: string[] = []): string | null {
  const scoped = topics.length ? entries.filter((h) => topics.includes(h.topic)) : entries
  const stats = mistakeStats(scoped)
  return stats.byType[0]?.key ?? null
}

export function topMistakes(entries: HistoryEntry[], topics: string[], n = 3): CountRow[] {
  const scoped = topics.length ? entries.filter((h) => topics.includes(h.topic)) : entries
  return mistakeStats(scoped).byType.slice(0, n)
}

/** What a parent or tutor sees: patterns and progress, never photos or answers. */
export function shareSnapshot(state: AppState, now = Date.now()) {
  const month = inRange(state.history, 30, now)
  const stats = mistakeStats(month)
  const all = mistakeStats(state.history)
  const top = stats.byType[0]
  return {
    name: state.settings.name || 'Student',
    updatedAt: now,
    month: { problems: stats.problems, mistakes: stats.mistakes, fixed: stats.fixed, allCorrect: stats.allCorrect,
      byType: stats.byType.slice(0, 8), byTopic: stats.byTopic.slice(0, 8) },
    allTime: { problems: all.problems, fixed: all.fixed },
    streaks: {
      days: dayStreak(state.history, now),
      fixes: fixStreak(state.history),
      cleanRun: top ? { type: top.key, count: cleanRun(state.history, top.key) } : null,
    },
    practice: {
      sessions: state.practice.filter((p) => now - p.at <= 30 * DAY).length,
      correct: state.practice.filter((p) => now - p.at <= 30 * DAY && p.correct).length,
    },
    recent: state.history.slice(0, 12).map((h) => ({
      at: h.createdAt, topic: h.topic, error: h.errors[0]?.type ?? null, fixed: h.fixed, allCorrect: h.allCorrect,
    })),
  }
}

export type ShareSnapshot = ReturnType<typeof shareSnapshot>
