import { useRef, useState } from 'react'

export interface Series { name: string; color: string; points: { x: number; y: number | null }[]; dashed?: boolean; width?: number }

/** Small precision line chart with a shared hover cursor (x snaps to the nearest data x). */
export function LineChart({ series, xLabel, yLabel, height = 150, onHover, activeX, xTicks, format = (v) => String(Math.round(v)) }: {
  series: Series[]; xLabel: string; yLabel: string; height?: number
  onHover?: (x: number | null) => void; activeX?: number | null; xTicks?: number[]; format?: (v: number) => string
}) {
  const ref = useRef<SVGSVGElement>(null)
  const [hx, setHx] = useState<number | null>(null)
  const W = 360, H = height, L = 38, R = 8, T = 10, B = 26
  const all = series.flatMap((s) => s.points.filter((p) => p.y != null)) as { x: number; y: number }[]
  if (!all.length) return <div className="text-sm text-muted">No data points.</div>
  const xs = [...new Set(all.map((p) => p.x))].sort((a, b) => a - b)
  const x0 = Math.min(...xs), x1 = Math.max(...xs)
  const ymax = Math.max(...all.map((p) => p.y)) * 1.1 || 1
  const sx = (x: number) => L + ((x - x0) / Math.max(x1 - x0, 1)) * (W - L - R)
  const sy = (y: number) => T + (1 - y / ymax) * (H - T - B)
  const yt = niceTicks(ymax)
  const ticks = xTicks ?? xs.filter((_, i) => i % Math.ceil(xs.length / 6) === 0)
  const cur = hx ?? activeX ?? null

  const move = (e: React.PointerEvent) => {
    const r = ref.current!.getBoundingClientRect()
    const vx = x0 + (((e.clientX - r.left) / r.width) * W - L) / (W - L - R) * (x1 - x0)
    const near = xs.reduce((a, b) => (Math.abs(b - vx) < Math.abs(a - vx) ? b : a), xs[0])
    setHx(near)
    onHover?.(near)
  }

  return (
    <div>
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="w-full touch-none" onPointerMove={move} onPointerLeave={() => { setHx(null); onHover?.(null) }} role="img" aria-label={`${yLabel} by ${xLabel}`}>
        {yt.map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={sy(v)} y2={sy(v)} stroke="#223443" />
            <text x={L - 4} y={sy(v) + 3} textAnchor="end" fontSize={9} fill="#94A8B6" className="num">{format(v)}</text>
          </g>
        ))}
        {ticks.map((v) => (
          <text key={v} x={sx(v)} y={H - 12} textAnchor="middle" fontSize={9} fill="#94A8B6" className="num">{v}</text>
        ))}
        <text x={W - R} y={H - 2} textAnchor="end" fontSize={9} fill="#5f7686">{xLabel}</text>
        <text x={L} y={8} fontSize={9} fill="#5f7686">{yLabel}</text>
        {series.map((s) => {
          const pts = s.points.filter((p) => p.y != null) as { x: number; y: number }[]
          return (
            <g key={s.name}>
              <polyline points={pts.map((p) => `${sx(p.x)},${sy(p.y)}`).join(' ')} fill="none" stroke={s.color} strokeWidth={s.width ?? 1.6} strokeDasharray={s.dashed ? '4 3' : undefined} />
              {pts.length < 16 && pts.map((p) => <circle key={p.x} cx={sx(p.x)} cy={sy(p.y)} r={2.2} fill={s.color} />)}
            </g>
          )
        })}
        {cur != null && (
          <g>
            <line x1={sx(cur)} x2={sx(cur)} y1={T} y2={H - B} stroke="#66DCE7" strokeWidth={1} />
            {series.map((s) => {
              const p = s.points.find((q) => q.x === cur)
              return p?.y != null ? <circle key={s.name} cx={sx(cur)} cy={sy(p.y)} r={3.5} fill="#080F1C" stroke={s.color} strokeWidth={1.6} /> : null
            })}
          </g>
        )}
      </svg>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-muted">
        {series.map((s) => (
          <span key={s.name} className="flex items-center gap-1">
            <svg width="14" height="6"><line x1="0" x2="14" y1="3" y2="3" stroke={s.color} strokeWidth="2" strokeDasharray={s.dashed ? '3 2' : undefined} /></svg>
            {s.name}
            {cur != null && (() => { const p = s.points.find((q) => q.x === cur); return p?.y != null ? <span className="num text-ink">{format(p.y)}</span> : null })()}
          </span>
        ))}
      </div>
    </div>
  )
}

function niceTicks(max: number) {
  const step = Math.pow(10, Math.floor(Math.log10(max / 3)))
  const s = [1, 2, 5, 10].map((m) => m * step).find((v) => max / v <= 5) ?? step * 10
  const out = []
  for (let v = 0; v <= max; v += s) out.push(Number(v.toFixed(6)))
  return out
}
