import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { api, cycleId, type DistrictRow, type Hazard } from '../../api'
import { fmtDate, fmtUtc, HAZARD_LABEL, pct, signed } from '../../format'
import { useDistricts, useSelection } from '../../hooks'
import { mapRegistry } from '../../map/layers'
import { useStore } from '../../store'
import { H, Loading, NotEvaluated, Problem, Prob, Seg } from '../ui'

type Sort = 'peak' | 'earliest' | 'state' | 'trend'
const series = (r: DistrictRow, h: Hazard) => (h === 'strike' ? r.p_strike ?? [] : r.p_rain[h])

export function DistrictsPanel() {
  const { eventId, cycle, event } = useSelection()
  const { hazard, districtId, set } = useStore()
  const [sort, setSort] = useState<Sort>('peak')
  const [q, setQ] = useState('')
  const table = useDistricts(eventId, cycle)
  const ready = (event.data?.cycles ?? []).filter((c) => c.status === 'ready').map((c) => cycleId(c.init))
  const prevCycle = cycle && ready.indexOf(cycle) > 0 ? ready[ready.indexOf(cycle) - 1] : null
  const prev = useDistricts(eventId, prevCycle)
  const search = useQuery({ queryKey: ['dsearch', q], queryFn: () => api.searchDistricts(q), enabled: q.length >= 2 })

  const rows = useMemo(() => {
    if (!table.data) return []
    const prevMap = new Map((prev.data?.rows ?? []).map((r) => [r.id, r]))
    const out = table.data.rows.map((r) => {
      const s = series(r, hazard)
      const peak = s.length ? Math.max(...s) : 0
      const earliest = s.findIndex((p) => p >= 0.3)
      const pr = prevMap.get(r.id)
      const trend = prev.data ? peak - (pr ? Math.max(0, ...series(pr, hazard)) : 0) : null
      return { r, s, peak, earliest: earliest < 0 ? 99 : earliest, trend }
    }).filter((x) => x.peak > 0)
    const cmp: Record<Sort, (a: typeof out[0], b: typeof out[0]) => number> = {
      peak: (a, b) => b.peak - a.peak,
      earliest: (a, b) => a.earliest - b.earliest || b.peak - a.peak,
      state: (a, b) => a.r.state.localeCompare(b.r.state) || b.peak - a.peak,
      trend: (a, b) => (b.trend ?? 0) - (a.trend ?? 0),
    }
    return out.sort(cmp[sort]).slice(0, 40)
  }, [table.data, prev.data, hazard, sort])

  const focus = (id: string) => {
    set({ districtId: id })
    const m = mapRegistry.main
    const d = search.data?.results.find((x) => x.id === id)
    if (m && d) m.fitBounds([[d.bbox[0], d.bbox[1]], [d.bbox[2], d.bbox[3]]], { padding: 120, maxZoom: 7, duration: 800 })
  }

  if (!eventId) {
    return (
      <>
        <DistrictSearch q={q} setQ={setQ} results={search.data?.results} onPick={focus} />
        <NotEvaluated what="District Risk Matrix" why="Select a replay or the latest run first; probabilities are computed per forecast cycle." />
      </>
    )
  }
  if (table.isLoading) return <Loading what="district probabilities" />
  if (table.error) return <Problem error={table.error} />
  const windows = table.data!.windows

  return (
    <>
      <DistrictSearch q={q} setQ={setQ} results={search.data?.results} onPick={focus} />
      {districtId && <DistrictDetail id={districtId} />}

      <section>
        <H aside={`${rows.length} districts`}>District Risk Matrix</H>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <Seg value={hazard} onChange={(v) => set({ hazard: v })} label="Hazard"
            options={[{ v: 'heavy', t: '≥64.5' }, { v: 'very_heavy', t: '≥115.6' }, { v: 'extremely_heavy', t: '≥204.5' }, { v: 'strike', t: 'Track ≤120 km' }]} />
          <label className="ml-auto flex items-center gap-1 text-[11px] text-muted">Sort
            <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} className="rounded border hairline bg-slate px-1 py-0.5">
              <option value="peak">peak probability</option>
              <option value="earliest">earliest ≥30%</option>
              <option value="state">state</option>
              <option value="trend" disabled={!prevCycle}>change vs previous cycle</option>
            </select>
          </label>
        </div>
        <p className="mb-2 text-[11px] text-muted">{HAZARD_LABEL[hazard]}. {hazard === 'strike' ? table.data!.definitions.p_strike : table.data!.definitions.p_rain}.</p>
        {rows.length === 0 ? (
          <p className="text-sm text-muted">No district reaches this condition in any member for this cycle.</p>
        ) : (
          <div className="overflow-x-auto scroll-thin">
            <table className="w-full border-separate border-spacing-[2px] text-[10px]">
              <thead>
                <tr>
                  <th className="sticky left-0 bg-ocean text-left font-normal label">District</th>
                  {windows.map((w) => <th key={w.index} className="font-normal num text-muted" title={`${fmtUtc(w.valid_start)} to ${fmtUtc(w.valid_end)}`}>D{w.index + 1}<br />{fmtDate(w.valid_end).slice(0, 6)}</th>)}
                  {prevCycle && <th className="font-normal label">Δ</th>}
                </tr>
              </thead>
              <tbody>
                {rows.map(({ r, s, trend }) => (
                  <tr key={r.id} className={districtId === r.id ? 'outline outline-1 outline-ion' : ''}>
                    <td className="sticky left-0 max-w-[110px] truncate bg-ocean pr-1">
                      <button onClick={() => set({ districtId: r.id })} className="truncate text-left text-[11px] hover:text-ion" title={`${r.name}, ${r.state}`}>{r.name}</button>
                    </td>
                    {windows.map((w) => <Cell key={w.index} p={s[w.index] ?? 0} />)}
                    {prevCycle && <td className="num text-right text-[10px]">{trend == null ? '' : <span className={trend > 0.05 ? 'text-coral' : trend < -0.05 ? 'text-teal' : 'text-muted'}>{trend > 0 ? '+' : ''}{Math.round(trend * 100)}</span>}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-2 text-[10px] text-muted">Cells: probability in % with a fill pattern (dots &lt;40%, hatching 40–70%, solid ≥70%). Δ: change in peak probability vs the previous cycle, in points.</p>
      </section>
    </>
  )
}

function Cell({ p }: { p: number }) {
  const v = Math.round(p * 100)
  const bg = p >= 0.7 ? 'rgba(216,87,151,0.85)' : p >= 0.4 ? 'rgba(243,184,92,0.75)' : p >= 0.1 ? 'rgba(102,220,231,0.45)' : p > 0 ? 'rgba(57,188,167,0.18)' : 'transparent'
  const pattern = p >= 0.7 ? undefined : p >= 0.4 ? 'repeating-linear-gradient(45deg, rgba(8,15,28,.35) 0 2px, transparent 2px 5px)' : p > 0 ? 'radial-gradient(rgba(8,15,28,.45) 1px, transparent 1px) 0 0/4px 4px' : undefined
  return (
    <td className="h-6 min-w-[24px] rounded-[2px] text-center num" style={{ background: pattern ? `${pattern}, ${bg}` : bg, color: p >= 0.4 ? '#080F1C' : '#c9d6df' }} title={`${v}% of members`}>
      {p > 0 ? v : ''}
    </td>
  )
}

function DistrictSearch({ q, setQ, results, onPick }: { q: string; setQ: (v: string) => void; results?: { id: string; name: string; state: string }[]; onPick: (id: string) => void }) {
  return (
    <section>
      <H>District Intelligence</H>
      <label className="flex items-center gap-2 rounded border hairline bg-slate px-2 py-1.5">
        <Search size={13} className="text-muted" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search a district, e.g. Puri, Chennai, Kachchh" aria-label="Search districts"
          className="w-full bg-transparent text-sm outline-none placeholder:text-muted" />
      </label>
      {q.length >= 2 && (
        <ul className="mt-1 max-h-40 overflow-y-auto rounded border hairline scroll-thin">
          {results?.length === 0 && <li className="px-2 py-1.5 text-sm text-muted">No district matches “{q}”.</li>}
          {results?.map((d) => (
            <li key={d.id}><button onClick={() => { onPick(d.id); setQ('') }} className="w-full px-2 py-1 text-left text-sm hover:bg-slate">{d.name}<span className="text-muted">, {d.state}</span></button></li>
          ))}
        </ul>
      )}
    </section>
  )
}

function DistrictDetail({ id }: { id: string }) {
  const { eventId, cycle } = useSelection()
  const { hazard } = useStore()
  const risk = useQuery({ queryKey: ['risk', id, eventId, cycle], queryFn: () => api.districtRisk(id, eventId!, cycle!), enabled: !!eventId && !!cycle })
  if (!eventId || !cycle) return null
  if (risk.isLoading) return <Loading what="district" />
  if (risk.error) return <Problem error={risk.error} />
  const d = risk.data!
  const r = d.risk
  const s = r ? series(r, hazard) : []
  const peakIdx = s.length ? s.indexOf(Math.max(...s)) : -1
  const earliest = s.findIndex((p) => p >= 0.3)
  return (
    <section className="rounded border border-ion/40 p-3">
      <div className="flex items-baseline justify-between">
        <h3 className="font-display text-lg font-semibold">{d.district.name}</h3>
        <span className="text-xs text-muted">{d.district.state}</span>
      </div>
      {d.no_signal || !r ? (
        <p className="mt-1 text-sm text-muted">No member brings heavy rain (≥ 64.5 mm/24 h) or the cyclone track within 120 km of this district in this cycle.</p>
      ) : (
        <>
          <p className="mt-1 text-sm leading-relaxed">
            {s.length && Math.max(...s) > 0
              ? <>Ensemble guidance suggests a peak probability of <Prob p={Math.max(...s)} /> for {HAZARD_LABEL[hazard].toLowerCase()} in the window ending {fmtUtc(d.windows[peakIdx].valid_end)}.{earliest >= 0 && <> It first reaches 30% in window D{earliest + 1}.</>}</>
              : <>No member meets {HAZARD_LABEL[hazard].toLowerCase()} here; other hazards may still show a signal.</>}
          </p>
          <table className="mt-2 w-full text-xs">
            <thead><tr className="label"><th className="text-left font-normal">Window</th><th className="text-right font-normal">≥64.5</th><th className="text-right font-normal">≥115.6</th><th className="text-right font-normal">≥204.5</th><th className="text-right font-normal">Track</th><th className="text-right font-normal">Rain p10–p90</th>{r.efi_max && <th className="text-right font-normal" title="Highest EFI-proxy (24 h rain vs ERA5 climate) over the district in the window; 0.5 unusual, 0.8 very unusual">EFI</th>}</tr></thead>
            <tbody>
              {d.windows.map((w) => {
                const any = r.p_rain.heavy[w.index] > 0 || (r.p_strike?.[w.index] ?? 0) > 0
                if (!any) return null
                return (
                  <tr key={w.index} className="border-t hairline">
                    <td className="py-0.5 num">{fmtDate(w.valid_end).slice(0, 6)}</td>
                    <td className="text-right num">{pct(r.p_rain.heavy[w.index])}</td>
                    <td className="text-right num">{pct(r.p_rain.very_heavy[w.index])}</td>
                    <td className="text-right num">{pct(r.p_rain.extremely_heavy[w.index])}</td>
                    <td className="text-right num">{r.p_strike ? pct(r.p_strike[w.index]) : 'n/a'}</td>
                    <td className="text-right num">{Math.round(r.rain_mm.p10[w.index])}–{Math.round(r.rain_mm.p90[w.index])} mm</td>
                    {r.efi_max && <td className={`text-right num ${r.efi_max[w.index] >= 0.8 ? 'text-coral' : r.efi_max[w.index] >= 0.5 ? 'text-amber' : ''}`}>{r.efi_max[w.index].toFixed(2)}</td>}
                  </tr>
                )
              })}
            </tbody>
          </table>
          {d.trend_vs_previous_cycle && (
            <div className="mt-2 text-[11px] text-muted">
              Change in peak probability since the {fmtUtc(d.trend_vs_previous_cycle.previous_cycle)} cycle:{' '}
              {Object.entries(d.trend_vs_previous_cycle.change).map(([k, v]) => <span key={k} className="mr-2 num">{k === 'strike' ? 'track' : k.replace('_', ' ')} {signed(v * 100, 'pts')}</span>)}
            </div>
          )}
        </>
      )}
      <p className="mt-2 text-[10px] text-muted">{d.provenance.model} · {d.provenance.members} members · init {fmtUtc(d.provenance.init_time)}. Boundaries: LGD 2021 via geoBoundaries.</p>
    </section>
  )
}
