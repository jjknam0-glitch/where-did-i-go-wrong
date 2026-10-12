// App state kept on this device (spec: the mistake profile lives in local
// storage until the student chooses to create an account). Pure functions
// only, so they are easy to test.

import type { LineType, Plan, Status, Tier } from './types'

export const STORAGE_KEY = 'wdigw:v1'
export const STATE_VERSION = 1

export interface HistoryLine {
  index: number
  math: string
  latex: string
  type: LineType
  status?: Status
  tier?: Tier
  error_type?: string
}

export interface HistoryEntry {
  id: string
  createdAt: number
  updatedAt: number
  source: 'photo' | 'sample' | 'typed' | 'practice'
  title?: string
  topic: string
  lines: HistoryLine[]
  firstError: number | null
  errors: { type: string; subtype?: string; line: number }[]
  allCorrect: boolean
  fixed: boolean
  fixedAt?: number
  hintsUsed: number
  photoId?: string
}

export interface SkillProgress {
  box: number
  due: number
  last: number
  attempts: number
  correct: number
}

export interface PracticeRecord {
  at: number
  skill: string
  correct: boolean
}

export interface Settings {
  name: string
  correctionsOptIn: boolean
  showCameraMetrics: boolean
  savePhotos: boolean
}

export interface ShareInfo {
  id: string
  secret: string
  createdAt: number
}

export interface FamilyMember {
  id: string
  label: string
}

export interface Account {
  token: string
  email: string
}

export interface AppState {
  version: number
  plan: Plan
  checkLog: number[]
  history: HistoryEntry[]
  srs: Record<string, SkillProgress>
  practice: PracticeRecord[]
  settings: Settings
  share: ShareInfo | null
  family: FamilyMember[]
  account: Account | null
  lastSyncAt: number | null
  onboarded: boolean
}

export const MAX_HISTORY = 500

export function initialState(): AppState {
  return {
    version: STATE_VERSION,
    plan: 'free',
    checkLog: [],
    history: [],
    srs: {},
    practice: [],
    settings: { name: '', correctionsOptIn: false, showCameraMetrics: false, savePhotos: false },
    share: null,
    family: [],
    account: null,
    lastSyncAt: null,
    onboarded: false,
  }
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

/** Accept whatever was stored before, falling back to defaults for anything malformed. */
export function normalizeState(raw: unknown): AppState {
  const base = initialState()
  if (!isObject(raw)) return base
  const plan = raw.plan === 'plus' || raw.plan === 'family' ? raw.plan : 'free'
  const history = Array.isArray(raw.history)
    ? (raw.history.filter((h) => isObject(h) && typeof h.id === 'string' && Array.isArray(h.lines)) as unknown as HistoryEntry[])
    : []
  const settings = isObject(raw.settings) ? { ...base.settings, ...(raw.settings as Partial<Settings>) } : base.settings
  return {
    ...base,
    plan,
    checkLog: Array.isArray(raw.checkLog) ? raw.checkLog.filter((n) => typeof n === 'number') : [],
    history: history.map((h) => ({ ...h, errors: Array.isArray(h.errors) ? h.errors : [], hintsUsed: h.hintsUsed ?? 0 })),
    srs: isObject(raw.srs) ? (raw.srs as Record<string, SkillProgress>) : {},
    practice: Array.isArray(raw.practice) ? (raw.practice as PracticeRecord[]) : [],
    settings,
    share: isObject(raw.share) && typeof raw.share.id === 'string' ? (raw.share as unknown as ShareInfo) : null,
    family: Array.isArray(raw.family) ? (raw.family as FamilyMember[]).filter((f) => f && typeof f.id === 'string') : [],
    account: isObject(raw.account) && typeof raw.account.token === 'string' ? (raw.account as unknown as Account) : null,
    lastSyncAt: typeof raw.lastSyncAt === 'number' ? raw.lastSyncAt : null,
    onboarded: Boolean(raw.onboarded),
  }
}

export function loadState(): AppState {
  try {
    const s = localStorage.getItem(STORAGE_KEY)
    return s ? normalizeState(JSON.parse(s)) : initialState()
  } catch {
    return initialState()
  }
}

export function saveState(state: AppState): boolean {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    return true
  } catch {
    return false
  }
}

export function uid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

// ----- reducer -----

export type Action =
  | { type: 'addHistory'; entry: HistoryEntry; countsAsCheck: boolean }
  | { type: 'updateHistory'; id: string; patch: Partial<HistoryEntry> }
  | { type: 'deleteHistory'; id: string }
  | { type: 'setPlan'; plan: Plan }
  | { type: 'recordPractice'; skill: string; correct: boolean; at?: number }
  | { type: 'updateSettings'; patch: Partial<Settings> }
  | { type: 'setShare'; share: ShareInfo | null }
  | { type: 'addFamily'; member: FamilyMember }
  | { type: 'removeFamily'; id: string }
  | { type: 'setAccount'; account: Account | null }
  | { type: 'merge'; remote: Partial<AppState>; at: number }
  | { type: 'setOnboarded' }
  | { type: 'reset' }

export const SRS_INTERVALS_DAYS = [1, 2, 4, 8, 16, 32]
const DAY = 86_400_000

export function nextSkillProgress(prev: SkillProgress | undefined, correct: boolean, now: number): SkillProgress {
  const p = prev ?? { box: 0, due: now, last: now, attempts: 0, correct: 0 }
  const box = correct ? Math.min(p.box + 1, SRS_INTERVALS_DAYS.length) : 0
  const days = correct ? SRS_INTERVALS_DAYS[Math.max(0, box - 1)] : 0.5
  return { box, due: now + days * DAY, last: now, attempts: p.attempts + 1, correct: p.correct + (correct ? 1 : 0) }
}

export function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'addHistory': {
      const history = [action.entry, ...state.history.filter((h) => h.id !== action.entry.id)].slice(0, MAX_HISTORY)
      const checkLog = action.countsAsCheck ? [...state.checkLog.filter((t) => Date.now() - t < 2 * DAY), action.entry.createdAt] : state.checkLog
      return { ...state, history, checkLog }
    }
    case 'updateHistory':
      return {
        ...state,
        history: state.history.map((h) => (h.id === action.id ? { ...h, ...action.patch, updatedAt: Date.now() } : h)),
      }
    case 'deleteHistory':
      return { ...state, history: state.history.filter((h) => h.id !== action.id) }
    case 'setPlan':
      return { ...state, plan: action.plan }
    case 'recordPractice': {
      const at = action.at ?? Date.now()
      return {
        ...state,
        practice: [...state.practice, { at, skill: action.skill, correct: action.correct }].slice(-2000),
        srs: { ...state.srs, [action.skill]: nextSkillProgress(state.srs[action.skill], action.correct, at) },
      }
    }
    case 'updateSettings':
      return { ...state, settings: { ...state.settings, ...action.patch } }
    case 'setShare':
      return { ...state, share: action.share }
    case 'addFamily':
      if (state.family.some((f) => f.id === action.member.id)) return state
      return { ...state, family: [...state.family, action.member] }
    case 'removeFamily':
      return { ...state, family: state.family.filter((f) => f.id !== action.id) }
    case 'setAccount':
      return { ...state, account: action.account, lastSyncAt: action.account ? state.lastSyncAt : null }
    case 'merge':
      return mergeRemote(state, action.remote, action.at)
    case 'setOnboarded':
      return { ...state, onboarded: true }
    case 'reset':
      return { ...initialState(), onboarded: true }
    default:
      return state
  }
}

// ----- account sync -----

/** What gets synced to an account (never photos, never the session token). */
export function syncPayload(state: AppState) {
  return {
    version: STATE_VERSION,
    plan: state.plan,
    history: state.history.map(({ photoId: _photoId, ...h }) => h),
    srs: state.srs,
    practice: state.practice,
    settings: { name: state.settings.name, correctionsOptIn: state.settings.correctionsOptIn },
    family: state.family,
  }
}

/** Union of local and remote data; for the same item the newer copy wins. */
export function mergeRemote(state: AppState, remote: Partial<AppState>, at: number): AppState {
  const byId = new Map<string, HistoryEntry>()
  for (const h of Array.isArray(remote.history) ? remote.history : []) {
    if (h && typeof h.id === 'string' && Array.isArray(h.lines)) byId.set(h.id, { ...h, errors: h.errors ?? [], hintsUsed: h.hintsUsed ?? 0 })
  }
  for (const h of state.history) {
    const other = byId.get(h.id)
    if (!other || (h.updatedAt ?? 0) >= (other.updatedAt ?? 0)) byId.set(h.id, { ...h, photoId: h.photoId ?? other?.photoId })
  }
  const history = [...byId.values()].sort((a, b) => b.createdAt - a.createdAt).slice(0, MAX_HISTORY)
  const srs = { ...(isObject(remote.srs) ? remote.srs : {}) } as Record<string, SkillProgress>
  for (const [k, v] of Object.entries(state.srs)) {
    if (!srs[k] || (v.last ?? 0) >= (srs[k].last ?? 0)) srs[k] = v
  }
  const seen = new Set<string>()
  const practice = [...(Array.isArray(remote.practice) ? remote.practice : []), ...state.practice]
    .filter((p) => {
      const key = `${p.at}|${p.skill}|${p.correct}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    .sort((a, b) => a.at - b.at)
    .slice(-2000)
  const family = [...state.family]
  for (const f of Array.isArray(remote.family) ? remote.family : []) {
    if (f && typeof f.id === 'string' && !family.some((x) => x.id === f.id)) family.push(f)
  }
  const remoteSettings = isObject(remote.settings) ? (remote.settings as Partial<Settings>) : {}
  // The plan is not merged here: the account record on the server is the source of truth.
  return {
    ...state,
    history,
    srs,
    practice,
    family,
    settings: { ...state.settings, name: state.settings.name || (remoteSettings.name ?? '') },
    lastSyncAt: at,
  }
}
