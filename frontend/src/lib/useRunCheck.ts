import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from './api'
import { buildHistoryEntry, checkAll, draftsNeedingAttention, historyId, linesOf } from './checking'
import { problemsOf, useFlow, type Session } from './flow'
import { savePhoto } from './photos'
import { checksLeftToday, hasFeature } from './profile'
import { useStore } from './store'
import type { DraftLine } from './types'

/** Check every problem in a session, log it to history and open the result. */
export function useRunCheck() {
  const { update, start, photoBlob } = useFlow()
  const { state, dispatch } = useStore()
  const navigate = useNavigate()
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(async (session: Session, opts: { isNew?: boolean } = {}) => {
    setError(null)
    if (checksLeftToday(state) <= 0 && !Object.keys(session.logged).length) {
      setError('You’ve used today’s free checks. They reset at midnight — or get unlimited checks with Plus.')
      return false
    }
    const attention = draftsNeedingAttention(session.drafts)
    if (attention.length) {
      setError(attention.some((d) => d.error) ? 'Some lines can’t be read as math yet — fix the ones marked in red.' : 'Please confirm the highlighted lines first.')
      return false
    }
    if (!session.drafts.some((d) => d.type !== 'note' && d.math.trim())) {
      setError('Add at least one line of work.')
      return false
    }
    setChecking(true)
    try {
      const results = await checkAll(session)
      if (state.settings.correctionsOptIn && session.source === 'photo') {
        for (const d of session.drafts) {
          if (d.original && d.original !== d.math) api.correction(d.original, d.math, d.type).catch(() => {})
        }
      }
      const checkedLines: Record<number, DraftLine[]> = {}
      const logged: Record<number, boolean> = { ...session.logged }
      let photoId: string | undefined
      for (const p of problemsOf(session.drafts)) {
        const lines = linesOf(session.drafts, p)
        checkedLines[p] = lines
        const result = results[p]
        if (result.advanced && !hasFeature(state.plan, 'advanced')) continue
        const id = historyId(session, p)
        const prev = state.history.find((h) => h.id === id)
        const entry = buildHistoryEntry(session, p, result, lines, prev)
        if (session.savePhoto && session.source === 'photo' && photoBlob && !entry.photoId) {
          if (photoId === undefined) photoId = (await savePhoto(session.id, photoBlob)) ? session.id : ''
          if (photoId) entry.photoId = photoId
        }
        dispatch({ type: 'addHistory', entry, countsAsCheck: !logged[p] && session.source !== 'practice' })
        logged[p] = true
      }
      const next = { ...session, results, checkedLines, logged }
      if (opts.isNew) start(next)
      else update(() => next)
      navigate('/result')
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The check failed. Please try again.')
      return false
    } finally {
      setChecking(false)
    }
  }, [dispatch, navigate, photoBlob, start, state, update])

  return { run, checking, error, setError }
}
