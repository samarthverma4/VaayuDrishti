import { useQuery } from '@tanstack/react-query'
import { api, cycleId } from './api'
import { useStore } from './store'

export const useIndex = () => useQuery({ queryKey: ['index'], queryFn: api.events })

export function useEvent(id: string | null) {
  return useQuery({ queryKey: ['event', id], queryFn: () => api.event(id!), enabled: !!id && id !== 'current' })
}

const enabled = (id: string | null, cycle: string | null) => !!id && !!cycle

export const useTracks = (id: string | null, cycle: string | null) =>
  useQuery({ queryKey: ['tracks', id, cycle], queryFn: () => api.tracks(id!, cycle!), enabled: enabled(id, cycle) })
export const useFields = (id: string | null, cycle: string | null) =>
  useQuery({ queryKey: ['fields', id, cycle], queryFn: () => api.fields(id!, cycle!), enabled: enabled(id, cycle) })
export const useIsobars = (id: string | null, cycle: string | null) =>
  useQuery({ queryKey: ['isobars', id, cycle], queryFn: () => api.isobars(id!, cycle!), enabled: enabled(id, cycle) })
export const useDistricts = (id: string | null, cycle: string | null) =>
  useQuery({ queryKey: ['districts', id, cycle], queryFn: () => api.districts(id!, cycle!), enabled: enabled(id, cycle) })
export const useVerification = (id: string | null, cycle: string | null) =>
  useQuery({ queryKey: ['verification', id, cycle], queryFn: () => api.verification(id!, cycle!), enabled: enabled(id, cycle) && id !== 'current' })
export const useSources = () => useQuery({ queryKey: ['sources'], queryFn: api.sources })

/** The selection the whole UI renders: event, cycle (defaults to the latest ready one), tracks, fields. */
export function useSelection() {
  const { eventId, cycle } = useStore()
  const index = useIndex()
  const event = useEvent(eventId)
  let effectiveCycle = cycle
  if (eventId && eventId !== 'current' && !cycle && event.data) {
    const ready = event.data.cycles.filter((c) => c.status === 'ready')
    effectiveCycle = ready.length ? cycleId(ready[Math.floor((ready.length - 1) / 2)].init) : null
  }
  if (eventId === 'current' && !cycle && index.data?.current) {
    effectiveCycle = index.data.current.systems[0]?.id ?? 'domain'
  }
  const tracks = useTracks(eventId, effectiveCycle && effectiveCycle !== 'domain' ? effectiveCycle : null)
  const fields = useFields(eventId, effectiveCycle)
  return { index, event, cycle: effectiveCycle, tracks, fields, eventId }
}

export const useSnapshots = (id: string | null, enabled: boolean) =>
  useQuery({ queryKey: ['snapshots', id], queryFn: () => api.snapshots(id!), enabled: !!id && enabled })
