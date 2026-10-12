import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, apiUrl } from './api'
import { draftFromRead, newSession, useFlow } from './flow'
import { prepareImage } from './image'
import { useStore } from './store'

export type Stage = 'idle' | 'preparing' | 'reading'

/** Photo or sample -> /api/read -> confirm screen. */
export function useCheckStarter() {
  const navigate = useNavigate()
  const { start, setPhotoBlob } = useFlow()
  const { state } = useStore()
  const [stage, setStage] = useState<Stage>('idle')
  const [error, setError] = useState<string | null>(null)

  const fromFile = useCallback(async (file: Blob, mode: 'problem' | 'page' = 'problem') => {
    setError(null)
    setStage('preparing')
    try {
      const img = await prepareImage(file)
      setStage('reading')
      const read = await api.read(img.blob, mode)
      if (!read.lines.length) {
        URL.revokeObjectURL(img.url)
        setError("We couldn't find any lines of work in that photo. Try again with the page filling more of the frame.")
        setStage('idle')
        return false
      }
      // Keep a data URL so a refresh doesn't lose the photo.
      let src = img.url
      try {
        const reader = new FileReader()
        src = await new Promise<string>((resolve) => {
          reader.onload = () => resolve(String(reader.result))
          reader.onerror = () => resolve(img.url)
          reader.readAsDataURL(img.blob)
        })
        URL.revokeObjectURL(img.url)
      } catch {
        /* keep the object URL */
      }
      setPhotoBlob(img.blob)
      start(newSession({
        source: 'photo',
        photo: { src, width: read.width, height: read.height },
        mode: read.mode === 'page' ? 'page' : 'problem',
        readSource: read.source,
        warnings: read.warnings,
        drafts: read.lines.map(draftFromRead),
        savePhoto: state.settings.savePhotos,
      }))
      setStage('idle')
      navigate('/confirm')
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong reading that photo.')
      setStage('idle')
      return false
    }
  }, [navigate, setPhotoBlob, start, state.settings.savePhotos])

  const fromSample = useCallback(async (id: string, title: string) => {
    setError(null)
    setStage('reading')
    try {
      const read = await api.readSample(id)
      setPhotoBlob(null)
      start(newSession({
        source: 'sample',
        title,
        photo: { src: apiUrl(`/api/samples/${id}.jpg`), width: read.width, height: read.height },
        mode: read.mode === 'page' ? 'page' : 'problem',
        readSource: read.source,
        warnings: read.warnings,
        drafts: read.lines.map(draftFromRead),
      }))
      setStage('idle')
      navigate('/confirm')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
      setStage('idle')
    }
  }, [navigate, setPhotoBlob, start])

  return { stage, error, setError, fromFile, fromSample }
}

export function cameraSupported(): boolean {
  return typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && window.isSecureContext
}
