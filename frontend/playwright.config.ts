import { defineConfig, devices } from '@playwright/test'
import { existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

// Runs the real backend and frontend. The backend needs its virtualenv:
//   cd backend && python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
const API_PORT = 8011
const WEB_PORT = 5181
const python = existsSync('../backend/.venv/bin/python') ? '.venv/bin/python' : 'python'
const dataDir = mkdtempSync(join(tmpdir(), 'wdigw-e2e-'))

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    ...devices['Pixel 7'],
  },
  webServer: [
    {
      command: `cd ../backend && DATA_DIR=${dataDir} ENGINE_WORKERS=2 RATE_READ_PER_10MIN=1000 RATE_CHECK_PER_10MIN=5000 RATE_AUTH_PER_10MIN=1000 RATE_SHARE_PER_HOUR=1000 ANTHROPIC_API_KEY= GEMINI_API_KEY= OPENAI_API_KEY= ${python} -m uvicorn app.main:app --port ${API_PORT}`,
      url: `http://localhost:${API_PORT}/api/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `VITE_DEV_API=http://localhost:${API_PORT} npx vite --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
