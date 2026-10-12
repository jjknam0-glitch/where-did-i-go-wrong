import { chromium, devices } from '@playwright/test'
import { writeFileSync, readFileSync } from 'node:fs'
const SP = process.env.SP
const browser = await chromium.launch({ args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', `--use-file-for-fake-video-capture=${SP}/f.mjpeg`] })
const ctx = await browser.newContext({ ...(process.env.MOBILE ? devices['Pixel 7'] : { viewport: { width: 390, height: 844 } }), permissions: ['camera'] })
const page = await ctx.newPage()
await page.addInitScript(() => { localStorage.setItem('wdigw:v1', JSON.stringify({ settings: { showCameraMetrics: true } })) })
await page.goto('http://localhost:5173/capture')
for (let i = 0; i < 8; i++) {
  await page.waitForTimeout(700)
  if (page.url().includes('confirm')) { console.log('captured'); break }
  console.log((await page.locator('pre').textContent().catch(() => '-')).replace(/\n/g, ' | '), '::', await page.locator('[aria-live="polite"] span').first().textContent().catch(() => ''))
  const vs = await page.evaluate(() => { const v = document.querySelector('video'); return v ? [v.videoWidth, v.videoHeight] : null })
  if (i === 0) console.log('video', vs)
}
await browser.close()
