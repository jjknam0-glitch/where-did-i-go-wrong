// Shapes returned by the API.

export type LineType = 'equation' | 'expression' | 'note'
export type Confidence = 'high' | 'low'
export type Status = 'start' | 'ok' | 'error' | 'warning' | 'follows_from_error' | 'uncertain' | 'skipped'
export type Tier = 'verified' | 'numeric' | 'ai_review'

export interface ReadLine {
  index: number
  box: [number, number, number, number]
  quad: [number, number][]
  crop: string
  problem: number
  type: LineType
  math: string
  latex: string
  confidence: Confidence
  alternatives: string[]
  needs_typing?: boolean
  unreadable?: boolean
  parse_error?: string
  lookalike?: { letter: string; digit: string }
}

export interface ReadResponse {
  problem_id: string
  width: number
  height: number
  paper_found: boolean
  mode: 'problem' | 'page' | 'line'
  source: 'ai' | 'sample' | 'manual'
  warnings: string[]
  lines: ReadLine[]
}

export interface CheckLine {
  index: number
  status: Status
  tier?: Tier
  error_type?: string
  error_name?: string
  subtype?: string
  hints?: string[]
  corrected?: string
  note?: string
  reason?: string
  message?: string
  lesson?: string
  compared_to?: number
}

export interface CheckResponse {
  lines: CheckLine[]
  first_error: number | null
  error_type: string | null
  sanity_check: string
  mode: string | null
  variable: string | null
  topic: string
  advanced: boolean
  all_correct: boolean
  counts: Record<string, number>
}

export interface FixResponse {
  valid: boolean
  fix: CheckLine
  check: CheckResponse | null
  lines: { index: number; math: string; type?: LineType }[]
}

export interface Health {
  ok: boolean
  version: string
  transcription: boolean
  read_models: string[]
  tiebreak_model: string | null
  ai_hints: boolean
}

export interface Sample {
  id: string
  title: string
  description: string
  page: boolean
  image: string
}

export interface PracticeProblem {
  id: string
  skill: string
  topic: string
  title: string
  kind: string
  prompt: string
  math: string
  latex: string
  level: number
}

export interface PracticeCheck {
  correct: boolean
  message: string
  equivalent?: boolean
}

export interface AnswerResponse {
  available: boolean
  latex?: string
  message?: string
}

export interface LessonSummary {
  id: string
  title: string
  topic: string
  summary: string
}

export interface Lesson extends LessonSummary {
  body: string[]
  practice: string
  example: { math: string; latex: string; status: Status; tier?: Tier; note?: string }[]
}

export interface User {
  id: number
  email: string
  plan: Plan
  corrections_opt_in: boolean
  created_at: number
}

export type Plan = 'free' | 'plus' | 'family'

// A line being edited on the confirm screen.
export interface DraftLine {
  key: string
  index: number
  math: string
  latex: string
  type: LineType
  confidence: Confidence
  alternatives: string[]
  confirmed: boolean
  crop?: string
  box?: [number, number, number, number]
  quad?: [number, number][]
  problem: number
  original?: string
  error?: string | null
  lookalike?: { letter: string; digit: string }
}
