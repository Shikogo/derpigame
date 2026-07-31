import { expect, test, type Page } from '@playwright/test'

import { createRoom, EXAMPLES, guess, joinRoom, readyUp, startRound } from './room'

/**
 * Two players in one room, in two browser contexts — separate storage, separate
 * sockets, the same room. This is the half of the game no unit test reaches:
 * whose turn it is only means anything with someone to hand it to.
 */
test('a turn belongs to one player at a time', async ({ browser }) => {
  const [alpha, beta] = await Promise.all([
    browser.newContext().then((c) => c.newPage()),
    browser.newContext().then((c) => c.newPage()),
  ])

  const code = await createRoom(alpha, 'Alpha')
  await joinRoom(beta, code, 'Beta')

  // Each sees the other in the room before anything starts. Exact, because the
  // ready hint names everyone too ("Ready up to start · Alpha and Beta…").
  await expect(alpha.getByText('Beta', { exact: true })).toBeVisible()
  await expect(beta.getByText('Alpha', { exact: true })).toBeVisible()

  await readyUp(alpha)
  await readyUp(beta)
  const image = await startRound(alpha)
  await expect(beta.getByPlaceholder(/Guess a tag|Type ahead/)).toBeVisible()

  // Exactly one of them is on the clock, and only that one can send.
  const onTurn = (await alpha.getByText('Your turn!').isVisible()) ? alpha : beta
  const waiting = onTurn === alpha ? beta : alpha
  await expect(onTurn.getByPlaceholder('Guess a tag…')).toBeVisible()
  await expect(waiting.getByPlaceholder('Type ahead for your turn…')).toBeVisible()
  await expect(waiting.getByRole('button', { name: 'Guess' })).toBeDisabled()

  // A scored guess reaches both feeds, and the turn moves on.
  const name = onTurn === alpha ? 'Alpha' : 'Beta'
  await guess(onTurn, EXAMPLES[image].plain)
  for (const page of [alpha, beta]) {
    await expect(page.getByTestId('guess-feed')).toContainText(`${name}: ${EXAMPLES[image].plain}`)
  }
  await expect(waiting.getByText('Your turn!')).toBeVisible()
  await expect(onTurn.getByPlaceholder('Type ahead for your turn…')).toBeVisible()
})

/** A player who leaves gives their seat back. */
test('leaving the room drops the player from it', async ({ browser }) => {
  const [alpha, beta] = await Promise.all([
    browser.newContext().then((c) => c.newPage()),
    browser.newContext().then((c) => c.newPage()),
  ])

  const code = await createRoom(alpha, 'Alpha')
  await joinRoom(beta, code, 'Beta')
  await expect(alpha.getByText('Beta', { exact: true })).toBeVisible()

  await leave(beta)
  await expect(alpha.getByText('Beta', { exact: true })).toBeHidden()
})

/** The header's leave button, then the confirmation the room asks for. */
async function leave(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Leave' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Leave' }).click()
}
