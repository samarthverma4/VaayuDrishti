// Headless screenshots of VYOMTRA views (dev server must be running on :5180).
//   node scripts/shots.mjs [outDir] [name=hash ...]
import { chromium } from '@playwright/test'
import { mkdirSync } from 'node:fs'

const out = process.argv[2] ?? '../docs/figures'
const views = process.argv.slice(3).length
  ? process.argv.slice(3).map((a) => [a.slice(0, a.indexOf('=')), a.slice(a.indexOf('=') + 1)])
  : [
      ['overview', 's=atmosphere'],
      ['dana-consensus', 's=events&e=dana-2024&c=2024102200&t=48'],
      ['montha-members', 's=events&e=montha-2025&c=2025102600&t=54&m=members'],
      ['fengal-uncertainty', 's=events&e=fengal-2024&c=2024112600&t=72&m=uncertainty'],
      ['dana-lens', 's=evolution&e=dana-2024&c=2024102100&t=72'],
      ['dana-districts', 's=districts&e=dana-2024&c=2024102200&t=48&d=odisha--kendrapara'],
      ['dana-verification', 's=verification&e=dana-2024&c=2024102200&t=48'],
      ['biparjoy-best-track', 's=events&e=biparjoy-2023'],
      ['current', 's=events&e=current&c=system-1&t=48'],
      ['advisory', 's=data&e=dana-2024&c=2024102200'],
    ]

mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
for (const [name, hash] of views) {
  await page.goto(`http://localhost:5180/#${hash}`)
  await page.reload()
  await page.waitForFunction(() => window.__map?.loaded() && window.__map.isStyleLoaded(), null, { timeout: 30000 })
  await page.waitForTimeout(2500)
  await page.screenshot({ path: `${out}/${name}.png` })
  console.log('shot', name)
}
await browser.close()
if (errors.length) console.log('page errors:\n' + [...new Set(errors)].join('\n'))
