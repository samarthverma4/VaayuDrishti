import { Search } from 'lucide-react'
import { useState } from 'react'
import { fmtDate } from '../format'
import { useIndex } from '../hooks'
import { useStore } from '../store'
import { Loading, Problem, TrackThumb } from './ui'

export function EventList() {
  const { data, error, isLoading } = useIndex()
  const { eventId, selectEvent, set } = useStore()
  const [q, setQ] = useState('')
  if (isLoading) return <div className="p-3"><Loading what="events" /></div>
  if (error) return <div className="p-3"><Problem error={error} /></div>
  const events = (data?.events ?? []).filter((e) => `${e.name} ${e.basin} ${e.start}`.toLowerCase().includes(q.toLowerCase()))
  const cur = data?.current

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b hairline p-3">
        <label className="flex items-center gap-2 rounded border hairline bg-slate px-2 py-1.5">
          <Search size={13} className="text-muted" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search events" aria-label="Search events"
            className="w-full bg-transparent text-sm outline-none placeholder:text-muted" />
        </label>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto scroll-thin">
        {cur && (
          <button
            onClick={() => { selectEvent('current'); set({ section: 'events' }) }}
            className={`block w-full border-b hairline px-3 py-3 text-left hover:bg-slate ${eventId === 'current' ? 'bg-slate' : ''}`}
            aria-current={eventId === 'current'}
          >
            <div className="flex items-center justify-between">
              <span className="font-display text-sm font-semibold">Latest ECMWF run</span>
              <span className="rounded-sm border border-teal/70 px-1 font-mono text-[9px] uppercase text-teal">Current</span>
            </div>
            <div className="mt-1 num text-[11px] text-muted">Init {fmtDate(cur.init)} 00Z · {cur.members} members</div>
            <div className="mt-1 text-xs">
              {cur.systems.length ? `${cur.systems.length} closed low${cur.systems.length > 1 ? 's' : ''} in the ensemble mean` : 'No closed low detected over the North Indian Ocean'}
            </div>
          </button>
        )}
        <div className="label px-3 pb-1 pt-3">Historical replays</div>
        {events.length === 0 && <div className="px-3 py-4 text-sm text-muted">No event matches “{q}”.</div>}
        {events.map((e) => {
          const ready = e.cycles_ready > 0
          return (
            <button
              key={e.id}
              onClick={() => { selectEvent(e.id); set({ section: 'events' }) }}
              aria-current={eventId === e.id}
              className={`flex w-full gap-3 border-b hairline px-3 py-2.5 text-left hover:bg-slate ${eventId === e.id ? 'bg-slate' : ''}`}
            >
              <TrackThumb coords={e.thumbnail} color={eventId === e.id ? '#66DCE7' : ready ? '#94A8B6' : '#4f6070'} />
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-display text-sm font-semibold">{e.name}</span>
                  <span className="num text-[10px] text-muted">{e.peak?.category?.code ?? ''}</span>
                </div>
                <div className="num text-[11px] text-muted">{fmtDate(e.start)} · {e.basin}</div>
                <div className="mt-0.5 flex items-center gap-1.5 text-[10px]">
                  {ready
                    ? <span className="num text-teal">{e.cycles_ready}/{e.cycles.length} cycles · ECMWF ENS</span>
                    : <span className="num text-amber">Best track only · awaiting TIGGE</span>}
                </div>
              </div>
            </button>
          )
        })}
      </div>
      <div className="border-t hairline p-3 text-[10px] leading-snug text-muted">
        Tracks: IBTrACS v04r01 (RSMC New Delhi). Forecasts: ECMWF IFS ENS, CC BY 4.0.
      </div>
    </div>
  )
}
