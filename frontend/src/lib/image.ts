// Image helpers: downscale before upload (phone photos can be 4-12 MB).

export const MAX_UPLOAD_SIDE = 2000

export interface PreparedImage {
  blob: Blob
  url: string // object URL for display; same pixels the server sees
  width: number
  height: number
}

function canvasToBlob(canvas: HTMLCanvasElement, type: string, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Could not encode the image'))), type, quality)
  })
}

async function decode(file: Blob): Promise<{ source: CanvasImageSource; width: number; height: number; close: () => void }> {
  if (typeof createImageBitmap === 'function') {
    try {
      const bmp = await createImageBitmap(file, { imageOrientation: 'from-image' })
      return { source: bmp, width: bmp.width, height: bmp.height, close: () => bmp.close() }
    } catch {
      /* fall through to <img> */
    }
  }
  const url = URL.createObjectURL(file)
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image()
      el.onload = () => resolve(el)
      el.onerror = () => reject(new Error("This image format isn't supported. Try a JPG or PNG."))
      el.src = url
    })
    return { source: img, width: img.naturalWidth, height: img.naturalHeight, close: () => URL.revokeObjectURL(url) }
  } catch (err) {
    URL.revokeObjectURL(url)
    throw err
  }
}

/** Decode (applying EXIF rotation), downscale to MAX_UPLOAD_SIDE and re-encode as JPEG. */
export async function prepareImage(file: Blob, maxSide = MAX_UPLOAD_SIDE, quality = 0.9): Promise<PreparedImage> {
  if (file.size === 0) throw new Error('That file is empty.')
  if (file.type && !file.type.startsWith('image/')) throw new Error('Please choose a photo.')
  const d = await decode(file)
  try {
    if (!d.width || !d.height) throw new Error("This image couldn't be read.")
    const scale = Math.min(1, maxSide / Math.max(d.width, d.height))
    const w = Math.max(1, Math.round(d.width * scale))
    const h = Math.max(1, Math.round(d.height * scale))
    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas unavailable')
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, w, h)
    ctx.drawImage(d.source, 0, 0, w, h)
    const blob = await canvasToBlob(canvas, 'image/jpeg', quality)
    return { blob, url: URL.createObjectURL(blob), width: w, height: h }
  } finally {
    d.close()
  }
}

/** A small JPEG for saving to history. */
export async function thumbnail(file: Blob, maxSide = 1000): Promise<Blob> {
  const p = await prepareImage(file, maxSide, 0.75)
  URL.revokeObjectURL(p.url)
  return p.blob
}

export function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(String(r.result))
    r.onerror = () => reject(r.error ?? new Error('read failed'))
    r.readAsDataURL(blob)
  })
}

export async function dataUrlToBlob(url: string): Promise<Blob> {
  const res = await fetch(url)
  return res.blob()
}
