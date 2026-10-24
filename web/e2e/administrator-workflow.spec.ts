import { expect, test } from '@playwright/test'

test('administrator signs in and creates a durable project', async ({ page }) => {
  const password = process.env.CALIPER_E2E_ADMIN_PASSWORD
  if (!password) throw new Error('Set CALIPER_E2E_ADMIN_PASSWORD to a disposable test-only value.')

  await page.goto('/')
  await page.getByLabel('Administrator password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Projects.' })).toBeVisible()

  const projectName = `Browser acceptance ${Date.now()}`
  await page.getByLabel('Project name').fill(projectName)
  await page.getByRole('button', { name: 'Create project' }).click()
  await expect(page.getByText(`${projectName} is ready in your workspace.`)).toBeVisible()
  await expect(page.getByRole('heading', { name: projectName })).toBeVisible()
})
