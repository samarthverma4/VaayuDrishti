import { Pause, Play } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { addHours, cycleLabel, fmtIst, fmtUtc, parseUtc } from '../format'
import { useSelection } from '../hooks'
import { useStore } from '../store'
import { outputLeads } from '../leads'

export function TimeRibbon() {
  const { tracks, fields, event, eventId } = useSelection()
  const { leadH, playing, speed, set } = useStore()
  const prov = fields.data?.provenance
  const init = tracks.data?.init ?? prov?.init_time
  const maxLead = prov?.leads_h[1] ?? 240
  const steps = prov?.lead_steps_h
  const leads = useMemo(() => steps?.length ? steps : outputLeads(maxLead), [steps, maxLead])
  const svgRef = useRef<SVGSVGElement>(null)
  const [width, setWidth] = useState(800)
  const [hover, setHover] = useState<number | null>(null)

  useEffect(() => {
    const el = svgRef.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [init])

  // playback steps through real output leads only
  useEffect(() => {
    if (!playing) return
    const id = window.setInterval(() => {
      const st = useStore.getState()
      const i = leads.indexOf(st.leadH)
      if (i >= leads.length - 1) set({ playing: false })
      else set({ leadH: leads[i + 1] })
    }, 420 / speed)
    return () => window.clearInterval(id)
  }, [playing, speed, leads, set])

  const pad = 14
  const x = useCallback((h: number) => pad + (h / maxLead) * (width - 2 * pad), [width, maxLead])
  const nearest = useCallback((px: number) => {
    const h = ((px - pad) / (width - 2 * pad)) * maxLead
    return leads.reduce((a, b) => (Math.abs(b - h) < Math.abs(a - h) ? b : a), leads[0])
  }, [width, maxLead, leads])

  const drag = useRef(false)
  const onPointer = (e: React.PointerEvent) => {
    const r = svgRef.current!.getBoundingClientRect()
    const h = nearest(e.clientX - r.left)
    if (e.type === 'pointerdown') {
      drag.current = true
      ;(e.target as Element).setPointerCapture(e.pointerId)
      set({ leadH: h, playing: false })
    } else if (e.type === 'pointermove') {
      setHover(h)
      if (drag.current) set({ leadH: h })
    } else if (e.type === 'pointerup') drag.current = false
  }
  const onKey = (e: React.KeyboardEvent) => {
    const i = leads.indexOf(leadH)
    if (e.key === 'ArrowRight') set({ leadH: leads[Math.min(i + 1, leads.length - 1)] })
    else if (e.key === 'ArrowLeft') set({ leadH: leads[Math.max(i - 1, 0)] })
    else if (e.key === 'Home') set({ leadH: 0 })
    else if (e.key === 'End') set({ leadH: leads[leads.length - 1] })
    else if (e.key === ' ') set({ playing: !playing })
    else return
    e.preventDefault()
  }

  if (!init) {
    return (
      <div className="flex h-full items-center px-4 text-sm text-muted">
        {!eventId
          ? 'Select an event or the current forecast to explore forecast time.'
          : event.data && event.data.cycles_ready === 0
            ? 'No forecast cycle loaded for this storm: only the observed best track is available.'
            : fields.error ? 'This forecast cycle is not available.' : 'Loading forecast cycle…'}
      </div>
    )
  }

  const tracked = tracks.data?.mean ?? []
  const aliveFrom = tracked[0]?.lead_h
  const aliveTo = tracked[tracked.length - 1]?.lead_h
  const lf = tracks.data?.landfall
  const obsLf = eventId !== 'current' ? event.data?.landfall : null
  const obsLfLead = obsLf ? (parseUtc(obsLf.time).getTime() - parseUtc(init).getTime()) / 3600e3 : null
  const valid = addHours(init, leadH)
  const shown = hover ?? leadH

  return (
    <div className="flex h-full items-stretch gap-3 px-3 py-2" >
      <div className="flex shrink-0 flex-col justify-center gap-1.5">
        <div className="flex items-center gap-1">
          <button
            onClick={() => set({ playing: !playing })}
            className="grid h-8 w-8 place-items-center rounded border hairline bg-slate hover:border-ion"
            aria-label={playing ? 'Pause forecast playback' : 'Play forecast'}
          >
            {playing ? <Pause size={14} /> : <Play size={14} />}
          </button>
          <div className="hidden rounded border hairline text-[11px] num sm:flex" role="group" aria-label="Playback speed">
            {([1, 2, 4] as const).map((s) => (
              <button key={s} onClick={() => set({ speed: s })} className={`px-1.5 py-1 ${speed === s ? 'bg-elevated text-ion' : 'text-muted'}`} aria-pressed={speed === s}>{s}×</button>
            ))}
          </div>
        </div>
        <div className="label hidden sm:block">Init {cycleLabel(init)}</div>
      </div>

      <div className="relative min-w-0 flex-1">
        <svg
          ref={svgRef}
          className="h-full w-full cursor-ew-resize touch-none select-none outline-none"
          role="slider" tabIndex={0}
          aria-label="Forecast lead time" aria-valuemin={0} aria-valuemax={maxLead} aria-valuenow={leadH}
          aria-valuetext={`T+${leadH} hours, valid ${fmtUtc(valid)}`}
          onPointerDown={onPointer} onPointerMove={onPointer} onPointerUp={onPointer} onPointerLeave={() => setHover(null)}
          onKeyDown={onKey}
        >
          {/* tracked span of the ensemble mean */}
          {aliveFrom != null && aliveTo != null && (
            <rect x={x(aliveFrom)} y={30} width={Math.max(2, x(aliveTo) - x(aliveFrom))} height={3} fill="#39BCA7" opacity={0.55} />
          )}
          <line x1={x(0)} x2={x(maxLead)} y1={31.5} y2={31.5} stroke="#314554" />
          <line x1={x(0)} x2={x(leadH)} y1={31.5} y2={31.5} stroke="#66DCE7" strokeWidth={1.5} />
          {leads.map((h) => (
            <line key={h} x1={x(h)} x2={x(h)} y1={h % 24 === 0 ? 22 : 27} y2={36} stroke={h % 24 === 0 ? '#94A8B6' : '#314554'} strokeWidth={h % 24 === 0 ? 1 : 0.7} />
          ))}
          {leads.filter((h) => h % (width < 760 ? 48 : 24) === 0).map((h) => (
            <g key={`l${h}`}>
              <text x={x(h)} y={16} textAnchor="middle" className="num" fontSize={10} fill="#94A8B6">T+{h}</text>
              {width > 700 && <text x={x(h)} y={50} textAnchor="middle" className="num" fontSize={9} fill="#5f7686">{fmtUtc(addHours(init, h)).slice(0, 6)}</text>}
            </g>
          ))}
          {/* forecast landfall: median and 10-90% range of members */}
          {lf && (
            <g aria-label="Forecast landfall time range">
              <rect x={x(lf.lead_h_p10)} y={39} width={Math.max(2, x(lf.lead_h_p90) - x(lf.lead_h_p10))} height={4} fill="#39BCA7" opacity={0.5} />
              <path d={`M${x(lf.median_lead_h)} 37 l4 4 l-4 4 l-4 -4z`} fill="#39BCA7" />
            </g>
          )}
          {obsLfLead != null && obsLfLead >= 0 && obsLfLead <= maxLead && (
            <g aria-label="Observed landfall">
              <line x1={x(obsLfLead)} x2={x(obsLfLead)} y1={20} y2={44} stroke="#F2F5F4" strokeDasharray="2 2" />
              <text x={x(obsLfLead) + 4} y={26} fontSize={9} fill="#F2F5F4" className="num">obs. landfall</text>
            </g>
          )}
          {hover != null && hover !== leadH && <line x1={x(hover)} x2={x(hover)} y1={20} y2={44} stroke="#94A8B6" opacity={0.6} />}
          <g transform={`translate(${x(leadH)},31.5)`}>
            <circle r={7} fill="#080F1C" stroke="#66DCE7" strokeWidth={2} />
            <circle r={2.2} fill="#66DCE7" />
          </g>
        </svg>
      </div>

      <div className="flex w-[118px] shrink-0 flex-col justify-center border-l hairline pl-2 sm:w-44 sm:pl-3">
        <div className="label">T+{shown} h {hover != null && hover !== leadH ? '(preview)' : ''}</div>
        <div className="num text-sm">{fmtUtc(addHours(init, shown))}</div>
        <div className="num text-xs text-muted">{fmtIst(addHours(init, shown))}</div>
      </div>
    </div>
  )
}
