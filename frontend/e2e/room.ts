import { expect, type Page } from '@playwright/test'

/**
 * Driving a room the way a player does — no store poking, no fabricated events.
 * Every assertion in the suite goes through the socket and the real backend.
 */

/**
 * The offline backend's images, by the label each one wears on the picture
 * (`backend/dev_server.py`). Which one a round gets depends on how many rounds
 * the server has already served, so a test asks rather than assumes.
 */
export const GOALS = {
  LIBRARY: ['book', 'library', 'magic', 'mare', 'solo', 'smiling', 'unicorn', 'twilight sparkle'],
  MEADOW: ['cloud', 'flying', 'grin', 'outdoors', 'pegasus', 'rainbow dash'],
} as const

export type ImageLabel = keyof typeof GOALS

/**
 * One guess of each shape, per image — the same vocabulary `dev_server.py`
 * documents. Keyed by image so a test asserts on whichever round it drew
 * instead of skipping when the rotation isn't where it hoped.
 */
export const EXAMPLES = {
  LIBRARY: {
    plain: 'book',
    bare: 'littlepip',
    bareTag: 'oc:littlepip',
    alias: 'ts',
    aliasTag: 'twilight sparkle',
    nearMiss: 'unicorm',
  },
  MEADOW: {
    plain: 'cloud',
    bare: 'testmare',
    bareTag: 'oc:testmare',
    alias: 'rd',
    aliasTag: 'rainbow dash',
    nearMiss: 'pegasis',
  },
} as const

/** Refused or wrong on either image, so no per-image variant is needed. */
export const WRONG = 'magik'
export const RATING_TAG = 'safe'
export const IGNORED_TAG = 'commission'

const guessBox = (page: Page) => page.getByPlaceholder(/Guess a tag|Type ahead/)
const feedEntries = (page: Page) => page.getByTestId('feed-entry')

/**
 * Close the how-to-play card, which opens over every fresh context's first page
 * — the same gesture a first-time player makes before they can do anything.
 */
async function dismissRules(page: Page): Promise<void> {
  const close = page.getByRole('button', { name: 'Close' })
  await close.click()
  await expect(close).toBeHidden()
}

/** Create a room as ``name``; resolves to its code once the lobby is up. */
export async function createRoom(page: Page, name: string): Promise<string> {
  await page.goto('/')
  await dismissRules(page)
  await page.getByPlaceholder('e.g. Twilight').fill(name)
  await page.getByRole('button', { name: 'Create a room' }).click()
  await expect(page.getByRole('button', { name: 'Ready up' })).toBeVisible()
  const code = new URL(page.url()).pathname.replace('/room/', '')
  expect(code).not.toBe('')
  return code
}

/** Join an existing room through its deep link, as a second player would. */
export async function joinRoom(page: Page, code: string, name: string): Promise<void> {
  await page.goto(`/room/${code}`)
  await dismissRules(page)
  await page.getByPlaceholder('Your name').fill(name)
  await page.getByRole('button', { name: 'Join' }).click()
  await expect(page.getByRole('button', { name: 'Ready up' })).toBeVisible()
}

export async function readyUp(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Ready up' }).click()
  await expect(page.getByRole('button', { name: 'Ready ✓' })).toBeVisible()
}

/**
 * Start the round and report which image came up. The caller readies up first;
 * with two players both must, since the start button waits on the presser only
 * but a round wants everyone in it.
 */
export async function startRound(page: Page): Promise<ImageLabel> {
  await page.getByRole('button', { name: /^Start (game|next round)$/ }).click()
  await expect(guessBox(page)).toBeVisible()
  return servedImage(page)
}

/** Which fixture image the round is showing, read off the picture's own label. */
export async function servedImage(page: Page): Promise<ImageLabel> {
  const sources = await page
    .locator('img')
    .evaluateAll((nodes) => nodes.map((n) => (n as HTMLImageElement).src))
  const decoded = sources.map((s) => decodeURIComponent(s)).join(' ')
  const label = (Object.keys(GOALS) as ImageLabel[]).find((name) => decoded.includes(name))
  if (!label) throw new Error('no fixture image on the page — is the backend `dev_server:app`?')
  return label
}

/**
 * Submit one guess and wait for its verdict to land in the feed. Waiting on the
 * feed rather than a timeout is what keeps a sequence of guesses in order —
 * every verdict, rejections included, adds an entry.
 */
export async function guess(page: Page, tag: string): Promise<void> {
  const before = await feedEntries(page).count()
  await guessBox(page).fill(tag)
  await guessBox(page).press('Enter')
  await expect(feedEntries(page)).toHaveCount(before + 1)
}

/** Clear the goal bucket, which is how a round is won. */
export async function winRound(page: Page, image: ImageLabel): Promise<void> {
  for (const tag of GOALS[image]) await guess(page, tag)
}
