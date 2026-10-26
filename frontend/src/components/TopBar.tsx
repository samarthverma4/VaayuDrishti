import { cycleId } from '../api'
import { cycleLabel, fmtUtc } from '../format'
import { useSelection } from '../hooks'
import { useStore } from '../store'
import { ModeBadge, Wordmark } from './ui'

export function TopBar() {
  const { event, cycle, fields, eventId, index } = useSelection()
  const { set } = useStore()
  const prov = fields.data?.provenance
  const cycles = eventId === 'current'
    ? (index.data?.current?.systems.map((s) => ({ v: s.id, t: `${s.id.replace('-', ' ')} · from T+${s.first_lead_h}` })) ?? []).concat([{ v: 'domain', t: 'All India (no track)' }])
    : (event.data?.cycles.filter((c) => c.status === 'ready').map((c) => ({ v: cycleId(c.init), t: cycleLabel(c.init) })) ?? [])

  return (
    <header className="flex h-12 shrink-0 items-center gap-4 border-b hairline bg-abyss px-3">
      <button onClick={() => { useStore.getState().selectEvent(null); set({ section: 'atmosphere' }) }} aria-label="VaayuDrishti home">
        <Wordmark />
      </button>
      <span className="hidden text-[11px] text-muted xl:inline">Atmospheric intelligence, made actionable</span>
      <div className="ml-auto flex min-w-0 items-center gap-3 text-xs">
        {prov && (
          <>
            <span className="hidden sm:inline"><ModeBadge mode={prov.mode} /></span>
            <span className="hidden num text-muted md:inline" title={prov.source}>
              {prov.model} · {prov.members} members · {prov.grid_deg}°
            </span>
          </>
        )}
        {cycles.length > 0 && (
          <label className="flex items-center gap-1.5">
            <span className="label">{eventId === 'current' ? 'System' : 'Cycle'}</span>
            <select
              value={cycle ?? ''}
              onChange={(e) => set({ cycle: e.target.value, leadH: 0, member: null })}
              className="rounded border hairline bg-slate px-1.5 py-1 num text-xs"
            >
              {cycles.map((c) => <option key={c.v} value={c.v}>{c.t}</option>)}
            </select>
          </label>
        )}
      </div>
      <div className="hidden max-w-[330px] text-right text-[10px] leading-tight text-muted lg:block">
        Experimental decision-support guidance. Not an official IMD warning.
        {prov?.retrieved_at && <span className="block num">Data retrieved {fmtUtc(prov.retrieved_at)}</span>}
      </div>
    </header>
  )
}
