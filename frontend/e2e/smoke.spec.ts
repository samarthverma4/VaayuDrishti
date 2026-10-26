import { expect, test } from '@playwright/test'

// Runs against the dev server (npm run dev) with the API on :8000.
declare global {
  interface Window { __map: import('maplibre-gl').Map }
}

test('Dana replay: drawn member tracks match the API', async ({ page, request }) => {
  test.skip(!!process.env.BASE_URL, 'reads the dev-only map handle (window.__map); production builds do not expose it')
  const api = await (await request.get('/api/v1/events/dana-2024/cycles/2024102200/tracks')).json()
  const expected = api.members.filter((m: { points: unknown[] }) => m.points.length > 1).length

  await page.goto('/#s=events&e=dana-2024&c=2024102200&t=48&m=members')
  await page.waitForFunction(() => window.__map?.loaded())
  await expect(page.getByRole('heading', { name: 'Dana' })).toBeVisible()
  await expect(page.getByText('Not an official IMD warning').first()).toBeVisible()

  const drawn = await page.evaluate(() => new Set(window.__map.querySourceFeatures('members').map((f) => f.properties.member)).size)
  expect(drawn).toBe(expected)
  const mean = await page.evaluate(() => window.__map.querySourceFeatures('mean').length)
  expect(mean).toBeGreaterThan(0)
})

test('time ribbon steps through output leads with the keyboard', async ({ page }) => {
  await page.goto('/#s=events&e=dana-2024&c=2024102200&t=0')
  const slider = page.getByRole('slider', { name: 'Forecast lead time' })
  await slider.focus()
  await page.keyboard.press('ArrowRight')
  await expect(slider).toHaveAttribute('aria-valuenow', '3')
  await page.keyboard.press('End')
  await expect(slider).toHaveAttribute('aria-valuenow', '240')
})

test('best-track-only storm says what is missing', async ({ page }) => {
  await page.goto('/#s=events&e=biparjoy-2023')
  await expect(page.getByText('No ensemble forecast loaded for this storm')).toBeVisible()
  await expect(page.getByText(/only the observed best track is available/)).toBeVisible()
})

test('TIGGE snapshot card shows the model low against the best track', async ({ page, request }) => {
  const r = await request.get('/api/v1/events/biparjoy-2023/snapshots')
  test.skip(r.status() === 404, 'no TIGGE snapshot built')
  const s = (await r.json()).snapshots[0]
  await page.goto('/#s=events&e=biparjoy-2023')
  const card = page.getByTestId('tigge-snapshot')
  await expect(card).toBeVisible()
  await expect(card).toContainText(`${s.model_min.msl_hpa.toFixed(1)} hPa`)
  await expect(card).toContainText('No forecast lead times')
})

test('rainfall verification table matches the API', async ({ page, request }) => {
  const r = await request.get('/api/v1/events/fengal-2024/cycles/2024113000/rain-verification')
  test.skip(r.status() === 404, 'no rain verification built')
  const d = (await r.json()).days[0]
  await page.goto('/#s=verification&e=fengal-2024&c=2024113000')
  const sec = page.getByTestId('rain-verification')
  await expect(sec).toContainText('Rainfall vs IMD observations')
  await expect(sec).toContainText(`${d.obs_mean_mm.toFixed(0)}/${d.fc_mean_mm.toFixed(0)}`)
})

test('map renders the forecast layer without errors', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  const png = page.waitForResponse((r) => r.url().includes('/png/') && r.status() === 200)
  await page.goto('/#s=events&e=dana-2024&c=2024102200&t=48')
  await expect(page.locator('canvas.maplibregl-canvas')).toBeVisible()
  await png
  expect(errors).toEqual([])
})
