import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState, type ReactNode } from 'react'
import { api, ApiError } from './api'
import { shareSnapshot } from './profile'
import { loadState, reducer, saveState, syncPayload, type Action, type AppState } from './state'

interface StoreValue {
  state: AppState
  dispatch: (a: Action) => void
  syncNow: () => Promise<void>
  syncing: boolean
  syncError: string | null
  storageOk: boolean
}

const StoreContext = createContext<StoreValue | null>(null)

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, undefined, loadState)
  const [syncing, setSyncing] = useState(false)
  const [syncError, setSyncError] = useState<string | null>(null)
  const [storageOk, setStorageOk] = useState(true)
  const stateRef = useRef(state)
  stateRef.current = state

  // Persist on every change.
  useEffect(() => {
    setStorageOk(saveState(state))
  }, [state])

  // Keep other tabs in sync.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'wdigw:v1' && e.newValue) {
        try {
          const remote = JSON.parse(e.newValue)
          dispatch({ type: 'merge', remote, at: stateRef.current.lastSyncAt ?? Date.now() })
          if (remote.plan && remote.plan !== stateRef.current.plan) dispatch({ type: 'setPlan', plan: remote.plan })
        } catch {
          /* ignore */
        }
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const syncNow = useCallback(async () => {
    const s = stateRef.current
    if (!s.account) return
    setSyncing(true)
    setSyncError(null)
    try {
      const remote = await api.getSync(s.account.token)
      if (remote.data && typeof remote.data === 'object') {
        dispatch({ type: 'merge', remote: remote.data as Partial<AppState>, at: Date.now() })
      }
      // Push the merged result on the next tick (after the reducer ran).
      await new Promise((r) => setTimeout(r, 0))
      await api.putSync(s.account.token, syncPayload(stateRef.current))
      dispatch({ type: 'merge', remote: {}, at: Date.now() })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        dispatch({ type: 'setAccount', account: null })
        setSyncError('You were signed out. Sign in again to keep syncing.')
      } else {
        setSyncError(err instanceof Error ? err.message : 'Sync failed')
      }
    } finally {
      setSyncing(false)
    }
  }, [])

  // Debounced background sync for signed-in students.
  const historyKey = `${state.history.length}:${state.history[0]?.updatedAt ?? 0}:${state.practice.length}:${state.plan}`
  useEffect(() => {
    if (!state.account) return
    const t = setTimeout(() => {
      api.putSync(state.account!.token, syncPayload(stateRef.current)).catch(() => {})
    }, 2500)
    return () => clearTimeout(t)
  }, [historyKey, state.account])

  // Keep an active parent/tutor share link up to date.
  useEffect(() => {
    if (!state.share) return
    const t = setTimeout(() => {
      const s = stateRef.current
      if (s.share) api.updateShare(s.share.id, s.share.secret, shareSnapshot(s)).catch((err) => {
        if (err instanceof ApiError && (err.status === 404 || err.status === 403)) dispatch({ type: 'setShare', share: null })
      })
    }, 1500)
    return () => clearTimeout(t)
  }, [historyKey, state.share, state.settings.name])

  const value = useMemo(() => ({ state, dispatch, syncNow, syncing, syncError, storageOk }), [state, syncNow, syncing, syncError, storageOk])
  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>
}

export function useStore(): StoreValue {
  const v = useContext(StoreContext)
  if (!v) throw new Error('useStore must be used inside StoreProvider')
  return v
}
