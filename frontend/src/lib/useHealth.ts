import { useEffect, useState } from 'react'
import { api } from './api'
import type { Health } from './types'

let cached: Health | null = null
let pending: Promise<Health> | null = null

/** Server status (is photo transcription configured?), fetched once per page load. */
export function useHealth() {
  const [health, setHealth] = useState<Health | null>(cached)
  const [error, setError] = useState(false)
  useEffect(() => {
    if (cached) return
    let alive = true
    pending = pending ?? api.health()
    pending
      .then((h) => {
        cached = h
        if (alive) setHealth(h)
      })
      .catch(() => {
        pending = null
        if (alive) setError(true)
      })
    return () => {
      alive = false
    }
  }, [])
  return { health, error }
}
