import * as maplibregl from 'maplibre-gl'
import type { Map as MLMap } from 'maplibre-gl'
import { useEffect, useRef, useState } from 'react'
import { cycleLabel, parseUtc } from '../format'
import { useFields, useSelection, useTracks } from '../hooks'
import { useStore } from '../store'
import { windowForLead } from './data'
import { mapRegistry, useCycleLayers, useMapReady } from './layers'
import { baseStyle, COLORS } from './style'

/** Forecast Stability Lens: the selected cycle (A) on the main map, a later or earlier cycle (B)
 *  in a synchronized map revealed right of a draggable divider, both at the same valid time. */
export function StabilityLens() {
  const { eventId, cycle, tracks } = useSelection()
  const { compareB, divider, layer, leadH, set } = useStore()
  const el = useRef<HTMLDivElement>(null)
  const wrap = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<MLMap | null>(null)
  const ready = useMapReady(map)
  const tb = useTracks(eventId, compareB)
  const fb = useFields(eventId, compareB)
  const shift = tracks.data && tb.data ? (parseUtc(tb.data.init).getTime() - parseUtc(tracks.data.init).getTime()) / 3600e3 : 0
  const w = windowForLead(fb.data, leadH - shift)
  const urls = layer !== 'none' ? fb.data?.layers[layer] : undefined

  useEffect(() => {
    if (!compareB || !el.current) return
    const main = mapRegistry.main
    const m = new maplibregl.Map({
      container: el.current, style: baseStyle(), interactive: false, attributionControl: false,
      center: main?.getCenter(), zoom: main?.getZoom() ?? 4,
    })
    setMap(m)
    const sync = () => main && m.jumpTo({ center: main.getCenter(), zoom: main.getZoom() })
    main?.on('move', sync)
    return () => {
      main?.off('move', sync)
      m.remove()
      setMap(null)
    }
  }, [compareB])

  useEffect(() => {
    if (!map || !ready) return
    map.setPaintProperty('mean', 'line-color', COLORS.compareB)
    map.setPaintProperty('mean-pos', 'circle-color', COLORS.compareB)
  }, [map, ready])

  useCycleLayers(map, ready, {
    tracks: tb.data, eventId, cycle: compareB,
    layerUrl: urls?.[Math.min(Math.max(w, 0), urls.length - 1)], bounds: fb.data?.bounds, leadShiftH: shift,
  })

  if (!compareB || !cycle) return null

  const onDrag = (e: React.PointerEvent) => {
    if (e.buttons !== 1 && e.type !== 'pointerdown') return
    const r = wrap.current!.getBoundingClientRect()
    set({ divider: Math.min(0.95, Math.max(0.05, (e.clientX - r.left) / r.width)) })
  }
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') set({ divider: Math.max(0.05, divider - 0.05) })
    else if (e.key === 'ArrowRight') set({ divider: Math.min(0.95, divider + 0.05) })
  }

  return (
    <div ref={wrap} className="pointer-events-none absolute inset-0 z-[5]">
      <div className="absolute inset-0" style={{ clipPath: `inset(0 0 0 ${divider * 100}%)` }} aria-hidden="true">
        <div ref={el} className="h-full w-full" />
      </div>
      <div className="absolute inset-y-0 w-px bg-ink/80" style={{ left: `${divider * 100}%` }} />
      <div
        className="pointer-events-auto absolute top-1/2 grid h-10 w-6 -translate-x-1/2 -translate-y-1/2 cursor-ew-resize place-items-center rounded border border-ink/70 bg-abyss text-[10px] text-ink"
        style={{ left: `${divider * 100}%` }}
        role="slider" tabIndex={0} aria-label="Stability lens divider" aria-valuemin={5} aria-valuemax={95} aria-valuenow={Math.round(divider * 100)}
        onPointerDown={(e) => { (e.target as Element).setPointerCapture(e.pointerId); onDrag(e) }} onPointerMove={onDrag} onKeyDown={onKey}
      >⇔</div>
      <div className="absolute bottom-3 left-3 rounded border border-amber/70 bg-abyss/85 px-2 py-1 num text-[11px] text-amber">A · {tracks.data ? cycleLabel(tracks.data.init) : cycle}</div>
      <div className="absolute bottom-3 right-3 rounded border border-ion/70 bg-abyss/85 px-2 py-1 num text-[11px] text-ion">
        B · {tb.data ? cycleLabel(tb.data.init) : compareB}{shift ? ` (lead ${leadH - shift >= 0 ? `T+${leadH - shift}` : 'before init'})` : ''}
      </div>
    </div>
  )
}
