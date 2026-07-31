import { expect, test } from '@playwright/test'

import {
  createRoom,
  EXAMPLES,
  GOALS,
  guess,
  IGNORED_TAG,
  RATING_TAG,
  readyUp,
  startRound,
  winRound,
  WRONG,
} from './room'

test('a round runs from the lobby to the results screen', async ({ page }) => {
  await createRoom(page, 'Alpha')
  await readyUp(page)
  const image = await startRound(page)

  await expect(page.getByText('Your turn!')).toBeVisible()
  await winRound(page, image)

  // Sole player, every tag scored, so the heading names you the winner.
  await expect(page.getByRole('heading', { name: 'You won! 🎉' })).toBeVisible()
  // The reveal: attribution the round only hands out once it's over.
  await expect(page.getByText(/on Derpibooru/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Start next round' })).toBeVisible()
})

test('each kind of guess gets its own verdict', async ({ page }) => {
  await createRoom(page, 'Alpha')
  await readyUp(page)
  const image = await startRound(page)
  const example = EXAMPLES[image]
  const feed = page.getByTestId('guess-feed')

  // Scored: a plain tag, a namespaced one typed bare, and one reached by alias.
  await guess(page, example.plain)
  await guess(page, example.bare)
  await guess(page, example.alias)
  await expect(feed).toContainText(`Alpha: ${example.plain}`)
  await expect(feed).toContainText(`Alpha: ${example.bareTag}`)
  await expect(feed).toContainText(`Alpha: ${example.aliasTag}`)

  // Refused, and free — none of these costs a strike or the turn.
  await guess(page, RATING_TAG)
  await guess(page, IGNORED_TAG)
  await guess(page, example.nearMiss)
  await expect(feed).toContainText(`${RATING_TAG} — rating tag`)
  await expect(feed).toContainText(`${IGNORED_TAG} — not guessable`)
  await expect(feed).toContainText(new RegExp(`Alpha: ${example.nearMiss} · \\d+%`))

  // Two of the three scored tags gate the win; the bare one is a bonus.
  await expect(page.getByText(`2 / ${GOALS[image].length}`)).toBeVisible()

  // ...and then one that is simply wrong.
  await guess(page, WRONG)
  await expect(feed).toContainText(`Alpha: ${WRONG}`)
})
