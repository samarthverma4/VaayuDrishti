import { create } from 'zustand'
import type { Hazard, LayerKey } from './api'

export type Section = 'atmosphere' | 'events' | 'evolution' | 'districts' | 'models' | 'verification' | 'data'
export type ConstellationMode = 'consensus' | 'members' | 'uncertainty'

interface State {
  section: Section
  eventId: string | null // 'current' for the latest run
  cycle: string | null // YYYYMMDDHH or 'system-N' / 'domain' for current
  leadH: number
  playing: boolean
  speed: 1 | 2 | 4
  layer: LayerKey | 'none'
  showIsobars: boolean
  mode: ConstellationMode
  member: number | null
  hoverLead: number | null
  districtId: string | null
  hazard: Hazard
  compareA: string | null
  compareB: string | null
  divider: number // 0..1 for the stability lens swipe
  snapshot: number // index of the single-field TIGGE snapshot shown for storms without forecast cycles
  panelOpen: boolean
  set: (p: Partial<State>) => void
  selectEvent: (id: string | null, cycle?: string | null) => void
}

// Shareable view state in the URL hash: #s=events&e=dana-2024&c=2024102200&t=48&m=members
const SECTIONS: Section[] = ['atmosphere', 'events', 'evolution', 'districts', 'models', 'verification', 'data']
function fromHash() {
  const p = new URLSearchParams(window.location.hash.slice(1))
  const s = p.get('s') as Section | null
  const mode = p.get('m') as ConstellationMode | null
  return {
    section: s && SECTIONS.includes(s) ? s : 'atmosphere',
    eventId: p.get('e'),
    cycle: p.get('c'),
    leadH: Number(p.get('t')) || 0,
    mode: mode && ['consensus', 'members', 'uncertainty'].includes(mode) ? mode : 'consensus',
    districtId: p.get('d'),
  } as const
}

const initial = fromHash()

export const useStore = create<State>((set) => ({
  section: initial.section,
  eventId: initial.eventId,
  cycle: initial.cycle,
  leadH: initial.leadH,
  playing: false,
  speed: 1,
  layer: 'strike',
  showIsobars: true,
  mode: initial.mode,
  member: null,
  hoverLead: null,
  districtId: initial.districtId,
  hazard: 'very_heavy',
  compareA: null,
  compareB: null,
  divider: 0.5,
  snapshot: 0,
  panelOpen: true,
  set: (p) => set(p),
  selectEvent: (id, cycle = null) =>
    set({ eventId: id, cycle, leadH: 0, playing: false, member: null, compareA: null, compareB: null, districtId: null, snapshot: 0 }),
}))

useStore.subscribe((st) => {
  const p = new URLSearchParams()
  p.set('s', st.section)
  if (st.eventId) p.set('e', st.eventId)
  if (st.cycle) p.set('c', st.cycle)
  if (st.leadH) p.set('t', String(st.leadH))
  if (st.mode !== 'consensus') p.set('m', st.mode)
  if (st.districtId) p.set('d', st.districtId)
  const h = '#' + p.toString()
  if (h !== window.location.hash) window.history.replaceState(null, '', h)
})
