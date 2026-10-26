import type { GeoJSONSource, ImageSource, Map as MLMap } from 'maplibre-gl'
import { useEffect, useState } from 'react'
import type { Tracks } from '../api'
import { useIsobars, useSelection } from '../hooks'
import { useStore } from '../store'
import {
  bestFC, bestPosFC, envelopeFC, isobarLead, landfallFC, meanFC, meanPosFC, memberPositionsFC, membersFC,
} from './data'
import { EMPTY } from './style'

export const mapRegistry: { main: MLMap | null } = { main: null }
export const INDIA: [[number, number], [number, number]] = [[62, 4], [98, 34]]

export function setData(map: MLMap, id: string, data: GeoJSON.FeatureCollection) {
  ;(map.getSource(id) as GeoJSONSource | undefined)?.setData(data)
}

export function useMapReady(map: MLMap | null) {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    if (!map) return
    if (map.isStyleLoaded()) setReady(true)
    else map.once('load', () => setReady(true))
  }, [map])
  return ready
}

/** Pushes one forecast cycle's layers into a map. Shared by the main map and the stability-lens map. */
export function useCycleLayers(map: MLMap | null, ready: boolean, opts: {
  tracks?: Tracks; eventId: string | null; cycle: string | null; layerUrl?: string; bounds?: [number, number][]
  leadShiftH?: number // for a later cycle shown at the same valid time: lead = leadH - shift
  fallbackIsobars?: GeoJSON.FeatureCollection // e.g. a single-field snapshot when no forecast cycle exists
}) {
  const store = useStore()
  const { mode, showIsobars } = store
  const leadH = store.leadH - (opts.leadShiftH ?? 0)
  const isobars = useIsobars(opts.eventId, opts.cycle)
  const { event } = useSelection()
  const best = opts.eventId !== 'current' ? event.data?.best_track : undefined

  useEffect(() => {
    if (!map || !ready) return
    setData(map, 'members', membersFC(opts.tracks, mode))
    setData(map, 'envelope', envelopeFC(opts.tracks, mode))
    setData(map, 'mean', meanFC(opts.tracks))
    setData(map, 'best', bestFC(best))
  }, [map, ready, opts.tracks, mode, best])

  useEffect(() => {
    if (!map || !ready) return
    setData(map, 'memberPos', memberPositionsFC(opts.tracks, leadH, mode))
    setData(map, 'meanPos', meanPosFC(opts.tracks, leadH))
    setData(map, 'bestPos', bestPosFC(best, opts.tracks?.init, leadH))
    setData(map, 'landfall', landfallFC(opts.tracks, opts.eventId !== 'current' ? event.data?.landfall : null, mode))
  }, [map, ready, opts.tracks, leadH, mode, best, event.data, opts.eventId])

  useEffect(() => {
    if (!map || !ready) return
    const fc = showIsobars ? (isobars.data?.isobars[String(isobarLead(leadH))] ?? opts.fallbackIsobars) : undefined
    setData(map, 'isobars', fc ?? EMPTY)
  }, [map, ready, isobars.data, leadH, showIsobars, opts.fallbackIsobars])

  useEffect(() => {
    if (!map || !ready) return
    const src = map.getSource('field') as ImageSource | undefined
    if (src && opts.layerUrl && opts.bounds) {
      src.updateImage({ url: opts.layerUrl, coordinates: opts.bounds as [[number, number], [number, number], [number, number], [number, number]] })
      map.setLayoutProperty('field', 'visibility', 'visible')
    } else map.setLayoutProperty('field', 'visibility', 'none')
  }, [map, ready, opts.layerUrl, opts.bounds])
}
