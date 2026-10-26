import * as maplibregl from 'maplibre-gl'
import type { FilterSpecification } from '@maplibre/maplibre-gl-style-spec'
import type { Map as MLMap, MapMouseEvent } from 'maplibre-gl'
import { useEffect, useMemo, useRef, useState } from 'react'
import { fmtIst, fmtUtc, addHours } from '../format'
import { useSelection, useSnapshots, useVerification } from '../hooks'
import { useStore } from '../store'
import { boundsOf, overviewFC, verifyLinksFC, windowForLead } from './data'
import { INDIA, mapRegistry, setData, useCycleLayers, useMapReady } from './layers'
import { baseStyle, COLORS, EMPTY } from './style'

const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches


export function MapCanvas() {
  const el = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<MLMap | null>(null)
  const ready = useMapReady(map)
  const { index, event, cycle, tracks, fields, eventId } = useSelection()
  const { leadH, layer, member, districtId, section, hoverLead, set, selectEvent } = useStore()
  const verification = useVerification(eventId, cycle)
  const [hoverInfo, setHoverInfo] = useState<{ x: number; y: number; text: string } | null>(null)

  useEffect(() => {
    const m = new maplibregl.Map({
      container: el.current!, style: baseStyle(), bounds: INDIA, fitBoundsOptions: { padding: 40 },
      attributionControl: { compact: true }, dragRotate: false, maxBounds: [[25, -25], [135, 55]],
      // dev only: keep the drawing buffer so the canvas can be captured for visual checks
      canvasContextAttributes: import.meta.env.DEV ? { preserveDrawingBuffer: true } : undefined, pitchWithRotate: false, maxZoom: 9, minZoom: 2.5,
    })
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')
    m.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left')
    m.touchZoomRotate.disableRotation()
    setMap(m)
    mapRegistry.main = m
    m.on('error', (e) => console.error('[map]', e.error?.message ?? e))
    if (import.meta.env.DEV) {
      // dev-only hooks for automated visual checks (see docs/testing.md)
      const w = window as unknown as { __map: MLMap; __capture: (name: string) => Promise<number> }
      w.__map = m
      w.__capture = async (name) => {
        m.triggerRepaint()
        // the drawing buffer is preserved, so the last rendered frame is readable even if idle never fires
        await new Promise((r) => setTimeout(r, 400))
        const src = m.getCanvas()
        const c = document.createElement('canvas')
        c.width = Math.min(1100, src.width)
        c.height = Math.round((c.width * src.height) / src.width)
        c.getContext('2d')!.drawImage(src, 0, 0, c.width, c.height)
        return (await fetch(`http://127.0.0.1:8765/${name}`, { method: 'POST', body: c.toDataURL('image/jpeg', 0.8) })).status
      }
    }
    return () => {
      mapRegistry.main = null
      m.remove()
    }
  }, [])

  // field overlay for the window that contains the current lead
  const w = windowForLead(fields.data, leadH)
  const urls = layer !== 'none' ? fields.data?.layers[layer] : undefined
  const layerUrl = urls?.[Math.min(w, urls.length - 1)]
  // single-field snapshot (e.g. one TIGGE analysis) for events without a forecast cycle
  const noCycles = !!event.data && event.data.cycles_ready === 0
  const snaps = useSnapshots(eventId, noCycles && !!event.data?.snapshots?.length)
  const snapIdx = useStore((st) => st.snapshot)
  const snap = noCycles ? (snaps.data?.snapshots[snapIdx] ?? snaps.data?.snapshots[0]) : undefined
  useCycleLayers(map, ready, { tracks: tracks.data, eventId, cycle, layerUrl, bounds: fields.data?.bounds, fallbackIsobars: snap?.isobars })
  useEffect(() => {
    if (!map || !ready) return
    setData(map, 'snapshot', snap ? { type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [snap.model_min.lon, snap.model_min.lat] } }] } : EMPTY)
  }, [map, ready, snap])

  // overview lines when nothing is selected
  const overview = useMemo(() => overviewFC(index.data?.events ?? []), [index.data])
  useEffect(() => {
    if (!map || !ready) return
    setData(map, 'overview', eventId ? EMPTY : overview)
  }, [map, ready, overview, eventId])

  // verification links (forecast mean to observed) in the verification section
  useEffect(() => {
    if (!map || !ready) return
    setData(map, 'verifyLinks', section === 'verification' ? verifyLinksFC(tracks.data, verification.data, hoverLead) : EMPTY)
  }, [map, ready, section, tracks.data, verification.data, hoverLead])

  // member selection highlight
  const prevMember = useRef<number | null>(null)
  useEffect(() => {
    if (!map || !ready) return
    if (prevMember.current != null) map.setFeatureState({ source: 'members', id: prevMember.current }, { selected: false })
    if (member != null) map.setFeatureState({ source: 'members', id: member }, { selected: true })
    prevMember.current = member
  }, [map, ready, member, tracks.data])

  // in the stability lens the main map shows cycle A in amber
  const { compareB } = useStore()
  useEffect(() => {
    if (!map || !ready) return
    const color = section === 'evolution' && compareB ? COLORS.compareA : COLORS.teal
    map.setPaintProperty('mean', 'line-color', color)
    map.setPaintProperty('mean-pos', 'circle-color', color)
  }, [map, ready, section, compareB])

  // district highlight
  useEffect(() => {
    if (!map || !ready) return
    const f: FilterSpecification = ['==', ['get', 'id'], districtId ?? '']
    map.setFilter('district-sel', f)
    map.setFilter('district-sel-fill', f)
  }, [map, ready, districtId])

  // camera: fly to the event (Atmospheric Focus) or back to India
  useEffect(() => {
    if (!map || !ready) return
    const dur = reducedMotion() ? 0 : 1100
    if (!eventId) {
      map.fitBounds(INDIA, { padding: 40, duration: dur })
      return
    }
    const coords = tracks.data?.mean.map((p) => [p.lon, p.lat]) ?? []
    const bestCoords = event.data?.best_track.map((p) => [p.lon, p.lat]) ?? []
    const b = boundsOf([...coords, ...bestCoords])
    if (b) map.fitBounds(b, { padding: { top: 80, bottom: 150, left: 60, right: 60 }, duration: dur, maxZoom: 6.2 })
    else if (event.data) {
      const bb = event.data.bbox
      map.fitBounds([[bb.lon_min, bb.lat_min], [bb.lon_max, bb.lat_max]], { padding: 40, duration: dur })
    }
  }, [map, ready, eventId, tracks.data?.init, event.data?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // interactions: hover and click on overview lines, members, districts
  useEffect(() => {
    if (!map || !ready) return
    let hovered: { source: string; id: string | number } | null = null
    const clear = () => {
      if (hovered) map.setFeatureState(hovered, { hover: false })
      hovered = null
      map.getCanvas().style.cursor = ''
      setHoverInfo(null)
    }
    const onMove = (e: MapMouseEvent) => {
      const feats = map.queryRenderedFeatures(e.point, { layers: ['overview-hit', 'members-hit'] })
      clear()
      const f = feats[0]
      if (!f) return
      const source = f.layer.id === 'overview-hit' ? 'overview' : 'members'
      hovered = { source, id: f.id as string | number }
      map.setFeatureState(hovered, { hover: true })
      map.getCanvas().style.cursor = 'pointer'
      const st = useStore.getState()
      let text = ''
      if (source === 'overview') text = `${f.properties.name}: select to open the replay`
      else {
        const tr = tracks.data
        const mem = tr?.members.find((m) => m.member === f.id)
        const p = mem?.points.find((q) => q.lead_h === st.leadH)
        text = `Member ${f.id}${f.id === 0 ? ' (control)' : ''}` + (p && tr ? ` · ${fmtUtc(addHours(tr.init, p.lead_h))} · ${p.msl_hpa.toFixed(0)} hPa · ${p.vmax_kt.toFixed(0)} kt` : ' · not tracked at this lead')
      }
      setHoverInfo({ x: e.point.x, y: e.point.y, text })
    }
    const onClick = (e: MapMouseEvent) => {
      const feats = map.queryRenderedFeatures(e.point, { layers: ['overview-hit', 'members-hit'] })
      const f = feats[0]
      if (f?.layer.id === 'overview-hit') {
        selectEvent(String(f.properties.id))
        set({ section: 'events' })
        return
      }
      if (f?.layer.id === 'members-hit') {
        set({ member: f.id as number, mode: 'members' })
        return
      }
      if (useStore.getState().section === 'districts' || map.getZoom() >= 4.6) {
        const d = map.queryRenderedFeatures(e.point, { layers: ['districts-hit'] })[0]
        if (d) set({ districtId: String(d.properties.id), section: 'districts' })
      }
    }
    map.on('mousemove', onMove)
    map.on('mouseout', clear)
    map.on('click', onClick)
    return () => {
      map.off('mousemove', onMove)
      map.off('mouseout', clear)
      map.off('click', onClick)
    }
  }, [map, ready, tracks.data, set, selectEvent])

  const validTime = tracks.data ? addHours(tracks.data.init, leadH) : fields.data ? addHours(fields.data.provenance.init_time, leadH) : null

  return (
    <div className="relative h-full w-full" role="region" aria-label="Interactive map of India and surrounding seas">
      <div className="absolute inset-0">
        {/* maplibre-gl.css forces position:relative on the map element, so it needs explicit full size */}
        <div ref={el} className="h-full w-full" />
      </div>
      {hoverInfo && (
        <div className="pointer-events-none absolute z-20 rounded border hairline bg-ocean/95 px-2 py-1 text-xs num" style={{ left: hoverInfo.x + 12, top: hoverInfo.y + 12 }}>
          {hoverInfo.text}
        </div>
      )}
      {validTime && (
        <div className="pointer-events-none absolute left-3 top-3 z-10 hidden rounded border hairline bg-abyss/80 px-2.5 py-1.5 md:block">
          <div className="label">Valid</div>
          <div className="num text-sm">{fmtUtc(validTime)}</div>
          <div className="num text-xs text-muted">{fmtIst(validTime)}</div>
        </div>
      )}
    </div>
  )
}
