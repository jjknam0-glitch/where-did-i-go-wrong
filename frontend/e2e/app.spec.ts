import { expect, test, type Page } from '@playwright/test'

async function setPlan(page: Page, plan: 'free' | 'plus') {
  await page.goto('/plans')
  if (plan === 'plus') await page.getByRole('button', { name: 'Try Plus' }).click()
  else await page.getByRole('button', { name: 'Use Free' }).click()
}

test.beforeEach(async ({ page }) => {
  page.on('pageerror', (e) => { throw e })
})

test('sample photo: confirm, red circle, hint, fix it yourself until everything checks out', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('sample-sign-error').click()
  await expect(page).toHaveURL(/\/confirm$/)
  await expect(page.getByTestId('confirm-line')).toHaveCount(3)
  await expect(page.getByTestId('check-button')).toHaveText('1 line needs a look')
  await page.getByText('Which did you write?').locator('..').getByRole('button').first().click()
  await expect(page.getByTestId('check-button')).toHaveText('Check my work')
  await page.getByTestId('check-button').click()

  await expect(page).toHaveURL(/\/result$/)
  await expect(page.getByText('This is where it went wrong.')).toBeVisible()
  await expect(page.locator('path.pen-stroke')).toHaveCount(1)
  await expect(page.getByTestId('hint-1')).toContainText("between lines 1 and 2")
  await expect(page.getByText('Hints 2 and 3 come with Plus').first()).toBeVisible()
  const lines = page.getByTestId('result-line')
  await expect(lines.nth(1)).toHaveAttribute('data-status', 'error')
  await expect(lines.nth(2)).toHaveAttribute('data-status', 'follows_from_error')

  // A wrong fix gets a hint, not a pass.
  await page.getByTestId('fix-button').click()
  await page.getByLabel('Your corrected step').fill('2x = 3')
  await page.getByTestId('submit-fix').click()
  await expect(page.getByText('Not quite yet.')).toBeVisible()

  await page.getByLabel('Your corrected step').fill('2x = 4')
  await page.getByTestId('submit-fix').click()
  await expect(page.getByTestId('hint-1')).toContainText('between lines 2 and 3')
  await page.getByTestId('fix-button').click()
  await page.getByLabel('Your corrected step').fill('x = 2')
  await page.getByTestId('submit-fix').click()
  await expect(page.getByText('Fixed — every step checks out.')).toBeVisible()

  // It's in history and the profile.
  await page.goto('/history')
  await expect(page.getByText('sign error (fixed)')).toBeVisible()
  await page.goto('/progress')
  await expect(page.getByText('mistakes you fixed')).toBeVisible()
})

test('free plan locks calculus and hints 2-3; Plus unlocks them', async ({ page }) => {
  await page.goto('/type')
  await page.getByLabel('Line 1', { exact: true }).fill('f(x) = x^2 sin(x)')
  await page.getByLabel('Line 2', { exact: true }).fill("f'(x) = 2x cos(x)")
  await page.getByTestId('type-check').click()
  await expect(page.getByText('Derivatives checking is part of Plus')).toBeVisible()

  await setPlan(page, 'plus')
  await page.goto('/type')
  await page.getByLabel('Line 1', { exact: true }).fill('f(x) = x^2 sin(x)')
  await page.getByLabel('Line 2', { exact: true }).fill("f'(x) = 2x cos(x)")
  await page.getByTestId('type-check').click()
  await page.getByTestId('show-hint-2').click()
  await expect(page.getByTestId('hint-2')).toContainText('product rule')
  await page.getByTestId('show-hint-3').click()
  await expect(page.getByTestId('hint-3')).toContainText('The derivative should be')

  await page.getByText('Show the final answer').click()
  await page.getByTestId('reveal-answer').click()
  await expect(page.getByTestId('final-answer').locator('.katex')).toBeVisible()
})

test('typing: unreadable lines are flagged before checking', async ({ page }) => {
  await page.goto('/type')
  await page.getByLabel('Line 1', { exact: true }).fill('2x + 3 = 7')
  await page.getByLabel('Line 2', { exact: true }).fill('2x = (4')
  await page.getByTestId('type-check').click()
  await expect(page.getByText("Some lines can’t be read as math yet")).toBeVisible()
  await page.getByLabel('Line 2', { exact: true }).fill('2x = 4')
  await page.getByLabel('Line 3', { exact: true }).fill('x = 2')
  await page.getByTestId('type-check').click()
  await expect(page.getByText('Every step checks out.')).toBeVisible()
})

test('whole-page sample gives a report per problem', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('sample-homework-page').click()
  await page.getByTestId('check-button').click()
  await expect(page.getByRole('radio', { name: /Problem 1/ })).toBeVisible()
  await expect(page.getByText('Every step checks out.')).toBeVisible()
  await page.getByRole('radio', { name: /Problem 2/ }).click()
  await expect(page.getByText('This is where it went wrong.')).toBeVisible()
})

test('practice, share link and family view (Plus)', async ({ page }) => {
  await setPlan(page, 'plus')
  await page.goto('/practice?skill=sign_error')
  const card = page.getByTestId('problem-card').first()
  await card.getByLabel('Your answer').fill('x = 12345')
  await card.getByRole('button', { name: 'Check answer' }).click()
  await expect(card.getByText('Not quite')).toBeVisible()

  await page.goto('/share')
  await page.getByPlaceholder('e.g. Sam').fill('Robin')
  await page.getByTestId('create-share').click()
  const url = (await page.getByTestId('share-url').textContent())!
  await page.goto(new URL(url).pathname)
  await expect(page.getByText("Robin's math progress")).toBeVisible()
  await page.getByRole('button', { name: 'Add to my family view' }).click()
  await page.goto('/family')
  await expect(page.getByRole('link', { name: /Robin/ })).toBeVisible()

  page.on('dialog', (d) => d.accept())
  await page.goto('/share')
  await page.getByRole('button', { name: 'Turn off this link' }).click()
  await page.goto(new URL(url).pathname)
  await expect(page.getByText("This link isn't active")).toBeVisible()
})

test('accounts are 13+', async ({ page }) => {
  await page.goto('/account')
  await page.getByLabel('Email').fill(`kid${Date.now()}@example.com`)
  await page.getByLabel('Password').fill('longenough1')
  await page.getByLabel('Date of birth').fill('2020-02-02')
  await page.getByRole('button', { name: 'Create account' }).last().click()
  await expect(page.getByRole('alert')).toContainText('Accounts are for ages 13 and up')
  await page.getByLabel('Date of birth').fill('2005-02-02')
  await page.getByRole('button', { name: 'Create account' }).last().click()
  await expect(page.getByRole('button', { name: 'Sync now' })).toBeVisible()
})
