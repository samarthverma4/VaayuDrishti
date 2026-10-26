// Time and number formatting. All stored times are UTC; IST is UTC+05:30.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export const parseUtc = (iso: string) => new Date(iso.endsWith('Z') || /[+-]\d\d:\d\d$/.test(iso) ? iso : iso + 'Z')

const pad = (n: number) => String(n).padStart(2, '0')

export function fmtUtc(iso: string | Date, withDay = true) {
  const d = typeof iso === 'string' ? parseUtc(iso) : iso
  const t = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`
  return withDay ? `${pad(d.getUTCDate())} ${MONTHS[d.getUTCMonth()]} ${t} UTC` : `${t} UTC`
}

export function fmtIst(iso: string | Date, withDay = true) {
  const d0 = typeof iso === 'string' ? parseUtc(iso) : iso
  const d = new Date(d0.getTime() + 5.5 * 3600e3)
  const t = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`
  return withDay ? `${pad(d.getUTCDate())} ${MONTHS[d.getUTCMonth()]} ${t} IST` : `${t} IST`
}

export function fmtDate(iso: string) {
  const d = parseUtc(iso)
  return `${pad(d.getUTCDate())} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`
}

export const cycleLabel = (iso: string) => {
  const d = parseUtc(iso)
  return `${pad(d.getUTCDate())} ${MONTHS[d.getUTCMonth()]} ${pad(d.getUTCHours())}Z`
}

export const addHours = (iso: string, h: number) => new Date(parseUtc(iso).getTime() + h * 3600e3)

export const pct = (p: number | null | undefined) => (p == null ? 'n/a' : `${Math.round(p * 100)}%`)
export const km = (v: number | null | undefined) => (v == null ? 'n/a' : `${Math.round(v)} km`)
export const signed = (v: number, unit: string, digits = 0) => `${v > 0 ? '+' : v < 0 ? '−' : '±'}${Math.abs(v).toFixed(digits)} ${unit}`
export const latlon = (lat: number, lon: number) => `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? 'N' : 'S'} ${Math.abs(lon).toFixed(2)}°${lon >= 0 ? 'E' : 'W'}`

export const HAZARD_LABEL: Record<string, string> = {
  heavy: 'Heavy rain ≥ 64.5 mm/24 h',
  very_heavy: 'Very heavy rain ≥ 115.6 mm/24 h',
  extremely_heavy: 'Extremely heavy rain ≥ 204.5 mm/24 h',
  strike: 'Track within 120 km',
}

export const LAYER_LABEL: Record<string, string> = {
  strike: 'Strike probability',
  p_heavy: 'P(rain ≥ 64.5 mm)',
  p_very_heavy: 'P(rain ≥ 115.6 mm)',
  p_extremely_heavy: 'P(rain ≥ 204.5 mm)',
  rain_mean: 'Ensemble-mean rain',
  efi: 'Extreme rain index (EFI-proxy)',
  sot: 'Shift of Tails (rain)',
}

// probability band for non-colour encoding
export function band(p: number) {
  if (p >= 0.7) return { label: 'High', glyph: '▲▲▲' }
  if (p >= 0.4) return { label: 'Elevated', glyph: '▲▲' }
  if (p >= 0.1) return { label: 'Low', glyph: '▲' }
  return { label: 'Very low', glyph: '·' }
}
