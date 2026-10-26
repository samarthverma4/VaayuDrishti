import type { ReactNode } from 'react'
import { ApiError } from '../api'
import { band, pct } from '../format'

export function Mark({ size = 22 }: { size?: number }) {
  // three trajectories converging on one point: ensemble members meeting a decision
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <g fill="none" strokeLinecap="round" strokeWidth="2.2">
        <path d="M4 7 C12 9 17 12 22 16" stroke="#66DCE7" />
        <path d="M4 25 C12 23 17 20 22 16" stroke="#39BCA7" />
        <path d="M3 16 H22" stroke="#F2F5F4" opacity=".85" />
      </g>
      <circle cx="24.5" cy="16" r="3.2" fill="#F2F5F4" />
    </svg>
  )
}

export function Wordmark() {
  return (
    <div className="flex items-center gap-2">
      <Mark />
      <span className="font-display text-[17px] font-semibold tracking-[0.04em]">VaayuDrishti</span>
    </div>
  )
}

export function H({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-2 flex items-baseline justify-between gap-2 border-b hairline pb-1.5">
      <h2 className="font-display text-[13px] font-semibold tracking-wide">{children}</h2>
      {aside && <div className="label">{aside}</div>}
    </div>
  )
}

export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: string }) {
  return (
    <div className="min-w-0">
      <div className="label">{label}</div>
      <div className={`num text-[15px] leading-tight ${tone ?? ''}`}>{value}</div>
      {sub && <div className="num text-[11px] text-muted">{sub}</div>}
    </div>
  )
}

export function ModeBadge({ mode }: { mode: 'historical-replay' | 'current-forecast' | 'illustrative' }) {
  const m = {
    'historical-replay': { t: 'Historical replay', c: 'border-blue/60 text-[#9cc0f5]' },
    'current-forecast': { t: 'Current forecast', c: 'border-teal/70 text-teal' },
    illustrative: { t: 'Illustrative · not real data', c: 'border-amber/70 text-amber' },
  }[mode]
  return <span className={`rounded-sm border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider ${m.c}`}>{m.t}</span>
}

export function Problem({ error, title }: { error: unknown; title?: string }) {
  const p = error instanceof ApiError ? error.problem : null
  return (
    <div className="rounded border border-dashed hairline p-3 text-sm">
      <div className="font-medium">{title ?? (p ? `Not available: ${p.missing}` : 'Not available')}</div>
      <div className="mt-1 text-muted">{p?.why ?? (error instanceof Error ? error.message : 'Unknown error')}</div>
      {p?.available && <div className="mt-1 text-xs text-muted">Still available: {p.available}</div>}
    </div>
  )
}

export function NotEvaluated({ what, why }: { what: string; why: string }) {
  return (
    <div className="rounded border border-dashed hairline p-3 text-sm">
      <div className="label mb-1">Not yet evaluated</div>
      <div className="font-medium">{what}</div>
      <div className="mt-1 text-muted">{why}</div>
    </div>
  )
}

export function Loading({ what }: { what: string }) {
  return <div className="py-3 text-sm text-muted">Loading {what}…</div>
}

/** Probability readout that never relies on colour alone: number + band glyph. */
export function Prob({ p, compact = false }: { p: number; compact?: boolean }) {
  const b = band(p)
  const tone = p >= 0.7 ? 'text-magenta' : p >= 0.4 ? 'text-amber' : p >= 0.1 ? 'text-ion' : 'text-muted'
  return (
    <span className={`num ${tone}`} title={`${b.label} (${pct(p)} of members)`}>
      {pct(p)}{!compact && <span className="ml-1 text-[9px] tracking-tighter">{b.glyph}</span>}
    </span>
  )
}

export function Seg<T extends string>({ value, options, onChange, label }: { value: T; options: { v: T; t: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="inline-flex rounded border hairline text-[11px]" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.v} onClick={() => onChange(o.v)} aria-pressed={value === o.v}
          className={`px-2 py-1 first:rounded-l last:rounded-r ${value === o.v ? 'bg-elevated text-ion' : 'text-muted hover:text-ink'}`}>
          {o.t}
        </button>
      ))}
    </div>
  )
}

export function TrackThumb({ coords, w = 64, h = 44, color = '#94A8B6' }: { coords: [number, number][]; w?: number; h?: number; color?: string }) {
  if (coords.length < 2) return <svg width={w} height={h} />
  const xs = coords.map((c) => c[0]), ys = coords.map((c) => c[1])
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
  const s = Math.min((w - 8) / Math.max(x1 - x0, 0.5), (h - 8) / Math.max(y1 - y0, 0.5))
  const ox = (w - (x1 - x0) * s) / 2, oy = (h - (y1 - y0) * s) / 2
  const pts = coords.map(([x, y]) => `${(ox + (x - x0) * s).toFixed(1)},${(h - oy - (y - y0) * s).toFixed(1)}`).join(' ')
  const last = pts.split(' ').pop()!.split(',')
  return (
    <svg width={w} height={h} aria-hidden="true" className="shrink-0 rounded-sm bg-abyss">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.4} />
      <circle cx={last[0]} cy={last[1]} r={2} fill={color} />
    </svg>
  )
}
