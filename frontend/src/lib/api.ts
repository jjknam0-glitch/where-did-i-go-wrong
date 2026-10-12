import type {
  AnswerResponse, CheckResponse, FixResponse, Health, Lesson, LessonSummary, LineType,
  PracticeCheck, PracticeProblem, ReadResponse, Sample, User,
} from './types'

// In development Vite proxies /api to the backend. In production, set
// VITE_API_URL to the backend's origin (e.g. https://api.example.xyz).
const BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export function apiUrl(path: string): string {
  return `${BASE}${path}`
}

async function request<T>(path: string, init: RequestInit & { timeoutMs?: number } = {}): Promise<T> {
  const { timeoutMs = 90_000, ...rest } = init
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  let res: Response
  try {
    res = await fetch(apiUrl(path), { ...rest, signal: controller.signal })
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw new ApiError('That took too long. Please try again.', 0)
    throw new ApiError("Can't reach the server. Check your connection and try again.", 0)
  } finally {
    clearTimeout(timer)
  }
  if (!res.ok) {
    let message = `Something went wrong (${res.status}).`
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') message = body.detail
      else if (Array.isArray(body?.detail)) message = 'Some of that input is invalid.'
    } catch {
      /* not JSON */
    }
    throw new ApiError(message, res.status)
  }
  return (await res.json()) as T
}

function json(method: string, body: unknown, headers: Record<string, string> = {}): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) }
}

function auth(token: string | null | undefined): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export interface LinePayload {
  index: number
  math: string
  type: LineType
}

export const api = {
  health: () => request<Health>('/api/health', { timeoutMs: 10_000 }),
  samples: () => request<Sample[]>('/api/samples'),

  read: (image: Blob, mode: 'problem' | 'page' | 'line' = 'problem') => {
    const form = new FormData()
    form.append('image', image, 'photo.jpg')
    form.append('mode', mode)
    return request<ReadResponse>('/api/read', { method: 'POST', body: form, timeoutMs: 120_000 })
  },
  readSample: (id: string) => {
    const form = new FormData()
    form.append('sample', id)
    return request<ReadResponse>('/api/read', { method: 'POST', body: form })
  },
  check: (lines: LinePayload[], acknowledge_sanity = false) =>
    request<CheckResponse>('/api/check', json('POST', { lines, acknowledge_sanity })),
  fix: (lines: LinePayload[], index: number, math: string) =>
    request<FixResponse>('/api/fix', json('POST', { lines, index, math })),
  parse: (lines: string[]) =>
    request<{ lines: { latex: string | null; error: string | null }[] }>('/api/parse', json('POST', { lines }), ),
  answer: (lines: LinePayload[]) => request<AnswerResponse>('/api/answer', json('POST', { lines })),
  explain: (body: {
    previous: string; student: string; corrected?: string | null; error_type?: string | null;
    hints: string[]; variable?: string | null
  }) => request<{ hints: string[]; source: 'ai' | 'template' }>('/api/explain', json('POST', { ...body, variable: body.variable ?? 'x' })),

  practice: (skill: string, count = 3, level = 1) =>
    request<{ skill: string; title: string; problems: PracticeProblem[] }>(
      `/api/practice?skill=${encodeURIComponent(skill)}&count=${count}&level=${level}`),
  harder: (topic: string, level = 2) =>
    request<{ problems: PracticeProblem[] }>(`/api/practice/harder?topic=${encodeURIComponent(topic)}&level=${level}`),
  drill: (skills: string[], count: number, level = 2) =>
    request<{ problems: PracticeProblem[] }>('/api/practice/drill', json('POST', { skills, count, level })),
  practiceCheck: (problem: PracticeProblem, answer: string) =>
    request<PracticeCheck>('/api/practice/check', json('POST', { problem: { kind: problem.kind, math: problem.math }, answer })),
  practiceAnswer: (problem: PracticeProblem) =>
    request<AnswerResponse>('/api/practice/answer', json('POST', { kind: problem.kind, math: problem.math })),

  lessons: () => request<LessonSummary[]>('/api/lessons'),
  lesson: (id: string) => request<Lesson>(`/api/lessons/${encodeURIComponent(id)}`),

  signup: (email: string, password: string, birth_date: string, corrections_opt_in: boolean) =>
    request<{ token: string; user: User }>('/api/auth/signup', json('POST', { email, password, birth_date, corrections_opt_in })),
  login: (email: string, password: string) =>
    request<{ token: string; user: User }>('/api/auth/login', json('POST', { email, password })),
  logout: (token: string) => request<{ ok: boolean }>('/api/auth/logout', { method: 'POST', headers: auth(token) }),
  me: (token: string) => request<User>('/api/auth/me', { headers: auth(token) }),
  updateMe: (token: string, body: Partial<Pick<User, 'plan' | 'corrections_opt_in'>>) =>
    request<User>('/api/auth/me', json('PATCH', body, auth(token))),
  deleteMe: (token: string) => request<{ ok: boolean }>('/api/auth/me', { method: 'DELETE', headers: auth(token) }),
  getSync: (token: string) => request<{ data: unknown; updated_at: number | null }>('/api/sync', { headers: auth(token) }),
  putSync: (token: string, data: unknown) =>
    request<{ updated_at: number }>('/api/sync', json('PUT', { data }, auth(token))),

  createShare: (snapshot: unknown) => request<{ id: string; secret: string }>('/api/share', json('POST', { snapshot })),
  getShare: (id: string) => request<{ snapshot: unknown; updated_at: number }>(`/api/share/${encodeURIComponent(id)}`),
  updateShare: (id: string, secret: string, snapshot: unknown) =>
    request<{ ok: boolean }>(`/api/share/${encodeURIComponent(id)}`, json('PUT', { snapshot }, { 'X-Share-Secret': secret })),
  revokeShare: (id: string, secret: string) =>
    request<{ ok: boolean }>(`/api/share/${encodeURIComponent(id)}`, { method: 'DELETE', headers: { 'X-Share-Secret': secret } }),

  correction: (original: string, corrected: string, type?: string) =>
    request<{ ok: boolean }>('/api/corrections', json('POST', { original, corrected, type })),
}
