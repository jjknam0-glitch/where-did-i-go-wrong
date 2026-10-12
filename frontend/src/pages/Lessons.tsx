import { BookOpen, ChevronRight } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { TexText } from '../components/Tex'
import { ErrorNote, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import type { LessonSummary } from '../lib/types'

export default function Lessons() {
  const [lessons, setLessons] = useState<LessonSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    api.lessons().then(setLessons).catch((e) => setError(e instanceof Error ? e.message : 'Could not load lessons'))
  }, [])
  const groups = lessons ? [...new Set(lessons.map((l) => l.topic))] : []
  return (
    <div>
      <PageHeader back="/more" title="Why does this rule work?" subtitle="Short lessons with a worked example verified by the math engine" />
      {error && <ErrorNote>{error}</ErrorNote>}
      {!lessons && !error && <Spinner />}
      {groups.map((g) => (
        <section key={g} className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">{g}</h2>
          <ul className="divide-y divide-line overflow-hidden rounded-3xl border border-line bg-surface">
            {lessons!.filter((l) => l.topic === g).map((l) => (
              <li key={l.id}>
                <Link to={`/lessons/${l.id}`} className="flex items-center gap-3 px-4 py-3.5 transition hover:bg-surface-2">
                  <BookOpen className="size-5 shrink-0 text-accent" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[15px] font-medium">{l.title}</span>
                    <span className="block truncate text-sm text-muted"><TexText text={l.summary} /></span>
                  </span>
                  <ChevronRight className="size-4 shrink-0 text-faint" />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}
