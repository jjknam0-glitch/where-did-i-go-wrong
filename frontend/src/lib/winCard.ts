// "I fixed my own mistake" cards students can share (growth loop: shareable wins).

export async function makeWinCard(opts: { headline: string; detail: string; topic: string }): Promise<Blob | null> {
  const W = 1080
  const H = 1350
  const c = document.createElement('canvas')
  c.width = W
  c.height = H
  const ctx = c.getContext('2d')
  if (!ctx) return null
  ctx.fillStyle = '#f7f6f2'
  ctx.fillRect(0, 0, W, H)
  // ruled paper
  ctx.strokeStyle = '#d7e3f3'
  ctx.lineWidth = 3
  for (let y = 260; y < H - 160; y += 90) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(W, y)
    ctx.stroke()
  }
  ctx.strokeStyle = '#f0b8b8'
  ctx.beginPath()
  ctx.moveTo(140, 0)
  ctx.lineTo(140, H)
  ctx.stroke()

  const font = (weight: number, size: number) => `${weight} ${size}px "Inter Variable", Inter, system-ui, sans-serif`
  ctx.fillStyle = '#16181d'
  ctx.font = font(700, 96)
  wrap(ctx, opts.headline, 200, 470, W - 300, 112)
  // the red circle
  ctx.strokeStyle = '#e5484d'
  ctx.lineWidth = 12
  ctx.lineCap = 'round'
  ctx.beginPath()
  ctx.ellipse(W / 2 + 40, 440, 430, 170, -0.05, 0.2, Math.PI * 2 + 0.5)
  ctx.stroke()

  ctx.fillStyle = '#5b606c'
  ctx.font = font(500, 54)
  wrap(ctx, opts.detail, 200, 820, W - 300, 70)
  ctx.font = font(600, 44)
  ctx.fillStyle = '#18794e'
  ctx.fillText(`✓ ${opts.topic}`, 200, 1010)

  ctx.fillStyle = '#16181d'
  ctx.font = font(700, 40)
  ctx.fillText('Where Did I Go Wrong?', 200, H - 90)
  return await new Promise((resolve) => c.toBlob(resolve, 'image/png'))
}

function wrap(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, maxW: number, lh: number) {
  const words = text.split(' ')
  let line = ''
  for (const w of words) {
    const test = line ? `${line} ${w}` : w
    if (ctx.measureText(test).width > maxW && line) {
      ctx.fillText(line, x, y)
      line = w
      y += lh
    } else line = test
  }
  if (line) ctx.fillText(line, x, y)
}

export async function shareOrDownload(blob: Blob, filename: string, text: string): Promise<'shared' | 'downloaded' | 'cancelled'> {
  const file = new File([blob], filename, { type: blob.type })
  const nav = navigator as Navigator & { canShare?: (d: ShareData) => boolean }
  if (nav.share && nav.canShare?.({ files: [file] })) {
    try {
      await nav.share({ files: [file], text })
      return 'shared'
    } catch {
      return 'cancelled'
    }
  }
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
  return 'downloaded'
}
