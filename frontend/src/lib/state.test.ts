import { beforeEach, describe, expect, it } from 'vitest'
import { initialState, loadState, mergeRemote, nextSkillProgress, normalizeState, reducer, saveState, STORAGE_KEY, syncPayload, type HistoryEntry } from './state'
import { checksLeftToday, cleanRun, countThisWeek, dayStreak, fixStreak, mistakeStats, patternMessage, shareSnapshot, visibleHistory, FREE_CHECKS_PER_DAY } from './profile'

const DAY = 86_400_000
function entry(id: string, daysAgo: number, error?: string, extra: Partial<HistoryEntry> = {}): HistoryEntry {
  const t = Date.now() - daysAgo * DAY
  return { id, createdAt: t, updatedAt: t, source: 'typed', topic: 'linear', lines: [{ index: 0, math: 'x=1', latex: 'x=1', type: 'equation' }],
    firstError: error ? 1 : null, errors: error ? [{ type: error, line: 1 }] : [], allCorrect: !error, fixed: false, hintsUsed: 1, ...extra }
}

describe('storage', () => {
  beforeEach(() => localStorage.clear())
  it('round-trips and survives garbage', () => {
    const s = reducer(initialState(), { type: 'setPlan', plan: 'plus' })
    expect(saveState(s)).toBe(true)
    expect(loadState().plan).toBe('plus')
    localStorage.setItem(STORAGE_KEY, '{not json')
    expect(loadState()).toEqual(initialState())
    expect(normalizeState({ plan: 'gold', history: [{ bad: true }], settings: { name: 'A' } })).toMatchObject({ plan: 'free', history: [], settings: { name: 'A' } })
  })
})

describe('reducer', () => {
  it('logs checks and counts the daily free limit', () => {
    let s = initialState()
    for (let i = 0; i < FREE_CHECKS_PER_DAY; i++) s = reducer(s, { type: 'addHistory', entry: entry(`e${i}`, 0), countsAsCheck: true })
    expect(checksLeftToday(s)).toBe(0)
    s = reducer(s, { type: 'addHistory', entry: entry('e0', 0), countsAsCheck: false })
    expect(s.history.length).toBe(FREE_CHECKS_PER_DAY)
    expect(checksLeftToday({ ...s, plan: 'plus' })).toBe(Infinity)
  })
  it('spaced repetition boxes', () => {
    const now = Date.now()
    const a = nextSkillProgress(undefined, true, now)
    expect(a.box).toBe(1)
    expect(a.due - now).toBe(1 * DAY)
    const b = nextSkillProgress(a, true, now)
    expect(b.box).toBe(2)
    expect(b.due - now).toBe(2 * DAY)
    const c = nextSkillProgress(b, false, now)
    expect(c.box).toBe(0)
    expect(c.due - now).toBe(0.5 * DAY)
  })
  it('free history shows 7 days', () => {
    const s = { ...initialState(), history: [entry('new', 1), entry('old', 10)] }
    expect(visibleHistory(s).map((h) => h.id)).toEqual(['new'])
    expect(visibleHistory({ ...s, plan: 'plus' }).length).toBe(2)
  })
})

describe('sync', () => {
  it('payload never includes photos or the token', () => {
    const s = { ...initialState(), account: { token: 'secret', email: 'a@b.co' }, history: [entry('a', 0, undefined, { photoId: 'p1' })] }
    const p = JSON.stringify(syncPayload(s))
    expect(p).not.toContain('secret')
    expect(p).not.toContain('p1')
  })
  it('merges by id with the newest copy winning', () => {
    const local = { ...initialState(), history: [entry('a', 0, 'sign_error', { updatedAt: 100, photoId: 'ph' }), entry('b', 1)] }
    const remote = { history: [entry('a', 0, 'sign_error', { updatedAt: 50, fixed: true }), entry('c', 2)] }
    const m = mergeRemote(local, remote, 1)
    expect(m.history.map((h) => h.id).sort()).toEqual(['a', 'b', 'c'])
    expect(m.history.find((h) => h.id === 'a')!.fixed).toBe(false)
    expect(m.history.find((h) => h.id === 'a')!.photoId).toBe('ph')
    expect(m.lastSyncAt).toBe(1)
  })
})

describe('profile', () => {
  const hist = [entry('1', 0, 'sign_error', { fixed: true }), entry('2', 0.5), entry('3', 1, 'sign_error'), entry('4', 2, 'arithmetic_slip'), entry('5', 9, 'sign_error')]
  it('stats', () => {
    const st = mistakeStats(hist)
    expect(st.mistakes).toBe(4)
    expect(st.byType[0]).toEqual({ key: 'sign_error', count: 3, pct: 75 })
    expect(st.fixed).toBe(1)
  })
  it('pattern message counts this week', () => {
    expect(countThisWeek(hist, 'sign_error')).toBe(2)
    expect(patternMessage(hist, 'sign_error')).toBe('This is your 2nd sign error this week.')
    expect(patternMessage(hist, 'exponent_rule')).toContain('first')
  })
  it('streaks', () => {
    expect(dayStreak(hist)).toBe(3)
    expect(cleanRun(hist, 'sign_error')).toBe(0)
    expect(cleanRun(hist.slice(1), 'arithmetic_slip')).toBe(2)
    expect(fixStreak(hist)).toBe(1)
  })
  it('share snapshot has no work or photos', () => {
    const snap = shareSnapshot({ ...initialState(), history: hist, settings: { ...initialState().settings, name: 'Sam' } })
    const s = JSON.stringify(snap)
    expect(snap.name).toBe('Sam')
    expect(s).not.toContain('x=1')
  })
})
