import { Dumbbell } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { StatusIcon, TierBadge } from '../components/StatusBits'
import { Tex, TexText } from '../components/Tex'
import { Card, ErrorNote, LinkButton, PageHeader, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { hasFeature } from '../lib/profile'
import { useStore } from '../lib/store'
import type { Lesson } from '../lib/types'

export default function LessonPage() {
  const { id } = useParams()
  const { state } = useStore()
  const [lesson, setLesson] = useState<Lesson | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    if (!id) return
    setLesson(null)
    api.lesson(id).then(setLesson).catch((e) => setError(e instanceof Error ? e.message : 'Could not load the lesson'))
  }, [id])

  if (error) return <div><PageHeader back title="Lesson" /><ErrorNote>{error}</ErrorNote></div>
  if (!lesson) return <Spinner />

  return (
    <article className="space-y-5">
      <PageHeader back title={lesson.title} subtitle={<TexText text={lesson.summary} />} />
      <div className="space-y-4 text-[16px] leading-relaxed">
        {lesson.body.map((p, i) => <p key={i}><TexText text={p} /></p>)}
      </div>
      <Card className="p-5">
        <h2 className="mb-1 font-semibold">Worked example</h2>
        <p className="mb-4 text-sm text-muted">Every step below was checked by the same engine that checks your work.</p>
        <ol className="space-y-3">
          {lesson.example.map((l, i) => (
            <li key={i} className="flex items-start gap-3">
              <StatusIcon status={l.status} />
              <div className="min-w-0 flex-1">
                <div className="math-scroll text-[17px]"><Tex latex={l.latex} /></div>
                <div className="mt-1 flex items-center gap-2">
                  {i === 0 ? <span className="text-xs text-muted">Start</span> : <TierBadge tier={l.tier} status={l.status} />}
                  {l.status === 'warning' && <span className="text-xs text-warn">This step can add a solution — check the answers.</span>}
                </div>
                {l.note && <p className="mt-1 text-sm text-muted"><TexText text={l.note} /></p>}
              </div>
            </li>
          ))}
        </ol>
      </Card>
      {hasFeature(state.plan, 'practice') ? (
        <LinkButton to={`/practice?skill=${lesson.practice}`} size="lg" className="w-full"><Dumbbell className="size-5" /> Practice this</LinkButton>
      ) : (
        <LinkButton to="/plans" variant="secondary" size="lg" className="w-full"><Dumbbell className="size-5" /> Practice this with Plus</LinkButton>
      )}
    </article>
  )
}
