import { expect, test } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

// Feed a sample photo to Chromium as a fake webcam and let the guided camera
// auto-capture it.
// A 1280x720 frame: the sample page on a desk, as a phone held sideways would see it.
const frame = readFileSync(join(import.meta.dirname, 'fixtures', 'camera-frame.jpg'))
const video = join(tmpdir(), 'wdigw-fake-camera.mjpeg')
writeFileSync(video, Buffer.concat(Array(30).fill(frame)))

test.use({
  permissions: ['camera'],
  launchOptions: {
    args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', `--use-file-for-fake-video-capture=${video}`],
  },
})

test('guided camera coaches, auto-captures and finds the lines', async ({ page }) => {
  await page.goto('/capture')
  await expect(page).toHaveURL(/\/confirm$/, { timeout: 20_000 })
  await expect(page.getByTestId('confirm-line')).toHaveCount(3)
})
