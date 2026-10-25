import type { BestTrackPoint, EventSummary, Fields, Tracks, Verification } from '../api'
import { addHours, parseUtc } from '../format'
import type { ConstellationMode } from '../store'
import { EMPTY } from './style'

type FC = GeoJSON.FeatureCollection

const line = (coords: number[][], props: Record<string, unknown> = {}): GeoJSON.Feature => ({
  type: 'Feature', properties: props, geometry: { type: 'LineString', coordinates: coords },
})
const point = (lon: number, lat: number, props: Record<string, unknown> = {}): GeoJSON.Feature => ({
  type: 'Feature', properties: props, geometry: { type: 'Point', coordinates: [lon, lat] },
})

export function overviewFC(events: EventSummary[]): FC {
  return { type: 'FeatureCollection', features: events.map((e) => ({ ...line(e.thumbnail, { id: e.id, name: e.name }), id: e.id })) }
}

export function membersFC(t: Tracks | undefined, mode: ConstellationMode): FC {
  if (!t || mode === 'consensus') return EMPTY
  return {
    type: 'FeatureCollection',
    features: t.members.filter((m) => m.points.length > 1).map((m) => ({
      ...line(m.points.map((p) => [p.lon, p.lat]), { member: m.member }),
      id: m.member,
    })),
  }
}

/** Position of each member at an output lead (exact; no interpolation between steps). */
export function memberPositionsFC(t: Tracks | undefined, leadH: number, mode: ConstellationMode): FC {
  if (!t || mode === 'consensus') return EMPTY
  const feats: GeoJSON.Feature[] = []
  for (const m of t.members) {
    const p = m.points.find((q) => q.lead_h === leadH)
    if (p) feats.push(point(p.lon, p.lat, { member: m.member, vmax: p.vmax_kt, msl: p.msl_hpa }))
  }
  return { type: 'FeatureCollection', features: feats }
}

export function meanFC(t: Tracks | undefined): FC {
  if (!t || t.mean.length < 2) return EMPTY
  return { type: 'FeatureCollection', features: [line(t.mean.map((p) => [p.lon, p.lat]))] }
}

export function meanPosFC(t: Tracks | undefined, leadH: number): FC {
  const p = t?.mean.find((q) => q.lead_h === leadH)
  return p ? { type: 'FeatureCollection', features: [point(p.lon, p.lat, { n: p.n_members })] } : EMPTY
}

export function envelopeFC(t: Tracks | undefined, mode: ConstellationMode): FC {
  if (!t?.envelope || mode === 'members') return EMPTY
  return { type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: t.envelope }] }
}

export function bestFC(best: BestTrackPoint[] | undefined): FC {
  if (!best?.length) return EMPTY
  return {
    type: 'FeatureCollection',
    features: [line(best.map((p) => [p.lon, p.lat])), ...best.map((p) => point(p.lon, p.lat, { wind: p.wind_kt }))],
  }
}

/** Observed position at a valid time, linearly interpolated between best-track fixes. */
export function observedAt(best: BestTrackPoint[] | undefined, valid: Date): { lat: number; lon: number; exact: boolean } | null {
  if (!best?.length) return null
  const t = valid.getTime()
  for (let i = 0; i < best.length; i++) {
    const ti = parseUtc(best[i].time).getTime()
    if (ti === t) return { lat: best[i].lat, lon: best[i].lon, exact: true }
    if (ti > t) {
      if (i === 0) return null
      const a = best[i - 1]
      const ta = parseUtc(a.time).getTime()
      const f = (t - ta) / (ti - ta)
      return { lat: a.lat + (best[i].lat - a.lat) * f, lon: a.lon + (best[i].lon - a.lon) * f, exact: false }
    }
  }
  return null
}

export function bestPosFC(best: BestTrackPoint[] | undefined, init: string | undefined, leadH: number): FC {
  if (!init) return EMPTY
  const o = observedAt(best, addHours(init, leadH))
  return o ? { type: 'FeatureCollection', features: [point(o.lon, o.lat)] } : EMPTY
}

export function landfallFC(t: Tracks | undefined, observed: { lat: number; lon: number } | null | undefined, mode: ConstellationMode): FC {
  const f: GeoJSON.Feature[] = []
  if (observed) f.push(point(observed.lon, observed.lat, { kind: 'observed' }))
  if (t?.landfall) f.push(point(t.landfall.mean_lon, t.landfall.mean_lat, { kind: 'forecast' }))
  if (t && mode === 'members') for (const m of t.members) if (m.landfall) f.push(point(m.landfall.lon, m.landfall.lat, { kind: 'member', member: m.member }))
  return { type: 'FeatureCollection', features: f }
}

export function verifyLinksFC(t: Tracks | undefined, v: Verification | undefined, activeLead: number | null): FC {
  if (!t || !v) return EMPTY
  const feats = v.by_lead.map((r) => {
    const m = t.mean.find((p) => p.lead_h === r.lead_h)
    return m ? line([[m.lon, m.lat], [r.obs_lon, r.obs_lat]], { lead: r.lead_h, active: r.lead_h === activeLead }) : null
  }).filter(Boolean) as GeoJSON.Feature[]
  return { type: 'FeatureCollection', features: feats }
}

/** 24 h window containing the lead: window w covers (24w, 24w+24]. */
export function windowForLead(fields: Fields | undefined, leadH: number): number {
  if (!fields?.windows.length) return 0
  const w = leadH <= 0 ? 0 : Math.ceil(leadH / 24) - 1
  return Math.min(Math.max(w, 0), fields.windows.length - 1)
}

export function isobarLead(leadH: number) {
  return Math.floor(leadH / 6) * 6
}

export function boundsOf(coords: number[][]): [[number, number], [number, number]] | null {
  if (!coords.length) return null
  let w = 180, s = 90, e = -180, n = -90
  for (const [x, y] of coords) {
    w = Math.min(w, x); e = Math.max(e, x); s = Math.min(s, y); n = Math.max(n, y)
  }
  return [[w, s], [e, n]]
}
