import { existsSync } from 'node:fs'

import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end tests, run against the offline backend (`backend/dev_server.py`),
 * whose images carry a known tag list. That fixture is what makes these worth
 * having: without it a round's outcome depends on whatever Derpibooru returned,
 * so there'd be nothing to assert.
 *
 * Both servers are started here rather than by hand, so `npm run e2e` is the
 * whole command. Locally they're reused if already running (`./run-local.sh
 * --offline`); CI always gets fresh ones.
 *
 * These are the offline lane's ports, the pair `--offline` uses, and they are
 * deliberately not the defaults a live session runs on: reuse means whatever
 * answers here gets driven by the suite, and a live backend answering would put
 * real Derpibooru traffic behind every round these tests start.
 */
const BACKEND = 'http://localhost:8100'
const FRONTEND = 'http://localhost:5273'

// CI installs Playwright's own chromium; a dev box usually has one already, and
// downloading a second copy to run a handful of tests isn't a fair trade.
const SYSTEM_CHROMIUM = '/usr/bin/chromium'
const executablePath = process.env.CI || !existsSync(SYSTEM_CHROMIUM) ? undefined : SYSTEM_CHROMIUM

export default defineConfig({
  testDir: './e2e',
  // Serial: the offline source hands out its images in rotation, so parallel
  // rounds would race for which one they get. The suite is small enough that
  // this costs nothing.
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: FRONTEND,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], launchOptions: { executablePath } },
    },
  ],
  webServer: [
    {
      command: '.venv/bin/uvicorn dev_server:app --port 8100',
      cwd: '../backend',
      url: `${BACKEND}/health`,
      reuseExistingServer: !process.env.CI,
      stdout: 'pipe',
    },
    {
      // The backend URL is passed explicitly: `frontend/.env` is gitignored, so
      // a runner has no other way to learn it.
      command: 'npm run dev -- --port 5273 --strictPort',
      env: { VITE_BACKEND_URL: BACKEND },
      url: FRONTEND,
      reuseExistingServer: !process.env.CI,
      stdout: 'pipe',
    },
  ],
})
