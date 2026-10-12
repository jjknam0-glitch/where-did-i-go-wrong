// Photos saved to history live only in this browser (IndexedDB), and only
// when the student chooses to save them.

const DB_NAME = 'wdigw-photos'
const STORE = 'photos'

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') return reject(new Error('IndexedDB unavailable'))
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => {
      req.result.createObjectStore(STORE)
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error ?? new Error('IndexedDB error'))
  })
}

async function tx<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open()
  try {
    return await new Promise<T>((resolve, reject) => {
      const t = db.transaction(STORE, mode)
      const req = fn(t.objectStore(STORE))
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error ?? new Error('IndexedDB error'))
    })
  } finally {
    db.close()
  }
}

export async function savePhoto(id: string, blob: Blob): Promise<boolean> {
  try {
    await tx('readwrite', (s) => s.put(blob, id))
    return true
  } catch {
    return false
  }
}

export async function getPhoto(id: string): Promise<Blob | null> {
  try {
    const v = await tx<unknown>('readonly', (s) => s.get(id))
    return v instanceof Blob ? v : null
  } catch {
    return null
  }
}

export async function deletePhoto(id: string): Promise<void> {
  try {
    await tx('readwrite', (s) => s.delete(id))
  } catch {
    /* ignore */
  }
}

export async function clearPhotos(): Promise<void> {
  try {
    await tx('readwrite', (s) => s.clear())
  } catch {
    /* ignore */
  }
}
