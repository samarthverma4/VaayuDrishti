import { useQueries, useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { api, cycleId } from '../../api'
import { cycleLabel, fmtUtc, HAZARD_LABEL, km, parseUtc, pct, signed } from '../../format'
import { useDistrictIndex } from '../../geoIndex'
import { useSelection } from '../../hooks'
import { useStore } from '../../store'
import { LineChart } from '../charts'
import { H, Loading, NotEvaluated, Problem, Stat } from '../ui'

export function EvolutionPanel() {
  const { event, cycle, eventId } = useSelection()
  const { compareB, set, hazard } = useStore()
  const idx = useDistrictIndex()
  const ready = (event.data?.cycles ?? []).filter((c) => c.status === 'ready' && c.has_tracks)
  const ids = ready.map((c) => cycleId(c.init))

  // default B: the next cycle after A (or the previous one if A is the last)
  useEffect(() => {
    if (!cycle || ids.length < 2) return
    if (compareB && compareB !== cycle && ids.includes(compareB)) return
    const i = ids.indexOf(cycle)
    set({ compareB: ids[i + 1] ?? ids[i - 1] ?? null })
  }, [cycle, ids.join(), compareB, set]) // eslint-disable-line react-hooks/exhaustive-deps

  const rainHazard = hazard === 'strike' ? 'very_heavy' : hazard
  const cmp = useQuery({
    queryKey: ['compare', eventId, cycle, compareB, rainHazard],
    queryFn: () => api.compare(eventId!, cycle!, compareB!, rainHazard),
    enabled: !!eventId && !!cycle && !!compareB && compareB !== cycle,
  })
  const all = useQueries({ queries: ids.map((c) => ({ queryKey: ['tracks', eventId, c], queryFn: () => api.tracks(eventId!, c), staleTime: Infinity })) })

  if (!eventId || eventId === 'current') {
    return <NotEvaluated what="Forecast Stability Lens" why="Select a historical replay with at least two forecast cycles. The latest run has a single cycle in this build." />
  }
  if (event.isLoading) return <Loading what="cycles" />
  if (ids.length < 2) return <NotEvaluated what="Forecast Stability Lens" why="This event needs at least two processed forecast cycles with tracks." />

  const obs = event.data?.landfall
  const name = (id: string) => idx.data?.find((d) => d.id === id)?.name ?? id.split('--')[1]
  const c = cmp.data

  return (
    <>
      <section>
        <H aside="VaayuDrishti diagnostic">Forecast Stability Lens</H>
        <p className="text-sm leading-relaxed text-muted">Drag the divider on the map: cycle A on the left, cycle B on the right, both shown at the same valid time.</p>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <label className="text-xs">
            <span className="label text-amber">Cycle A (map, left)</span>
            <select value={cycle ?? ''} onChange={(e) => set({ cycle: e.target.value })} className="mt-1 w-full rounded border hairline bg-slate px-1.5 py-1 num">
              {ids.map((v) => <option key={v} value={v}>{cycleLabel(ready[ids.indexOf(v)].init)}</option>)}
            </select>
          </label>
          <label className="text-xs">
            <span className="label text-ion">Cycle B (right)</span>
            <select value={compareB ?? ''} onChange={(e) => set({ compareB: e.target.value })} className="mt-1 w-full rounded border hairline bg-slate px-1.5 py-1 num">
              {ids.filter((v) => v !== cycle).map((v) => <option key={v} value={v}>{cycleLabel(ready[ids.indexOf(v)].init)}</option>)}
            </select>
          </label>
        </div>
      </section>

      <section>
        <H aside={c ? `${c.matched_valid_times} matched valid times` : undefined}>Stability signature</H>
        {cmp.isLoading && <Loading what="comparison" />}
        {cmp.error && <Problem error={cmp.error} />}
        {c && (
          <>
            {c.landfall && (
              <div className="mb-3 grid grid-cols-3 gap-3">
                <Stat label="Landfall shift" value={km(c.landfall.shift_km)} sub="mean landfall point" />
                <Stat label="Landfall time" value={signed(c.landfall.time_change_h, 'h', 1)} sub="B minus A" />
                <Stat label="Members landfalling" value={signed(c.landfall.fraction_change * 100, 'pts')} sub="B minus A" />
              </div>
            )}
            <LineChart
              xLabel="hours after cycle B init" yLabel="km"
              series={[
                { name: 'Mean-track displacement A→B', color: '#F3B85C', points: c.by_valid_time.map((r) => ({ x: r.lead_b_h, y: r.displacement_km })) },
                { name: 'Spread change (B − A)', color: '#66DCE7', dashed: true, points: c.by_valid_time.map((r) => ({ x: r.lead_b_h, y: Math.abs(r.spread_change_km) })) },
              ]}
            />
            <p className="mt-1 text-[10px] text-muted">Spread change plotted as magnitude; B is {c.by_valid_time.every((r) => r.spread_change_km <= 0) ? 'tighter' : 'not uniformly tighter'} than A over the matched times. {c.note}</p>
            {c.districts && (
              <div className="mt-3 text-sm">
                <div className="label mb-1">Districts with P ≥ {pct(c.districts.p_min)} for {HAZARD_LABEL[c.districts.threshold]}</div>
                <div><span className="text-coral">Added in B:</span> {c.districts.added.length ? c.districts.added.map(name).join(', ') : 'none'}</div>
                <div><span className="text-teal">Dropped in B:</span> {c.districts.removed.length ? c.districts.removed.map(name).join(', ') : 'none'}</div>
                <div className="text-muted">Kept: {c.districts.kept.length}</div>
              </div>
            )}
          </>
        )}
      </section>

      <section>
        <H aside={obs ? 'vs observed landfall' : undefined}>Landfall forecast across cycles</H>
        <table className="w-full text-xs">
          <thead><tr className="label"><th className="py-1 text-left font-normal">Cycle</th><th className="text-left font-normal">Median landfall</th><th className="text-right font-normal">Members</th>{obs && <th className="text-right font-normal">Time error</th>}</tr></thead>
          <tbody>
            {all.map((q, i) => {
              const t = q.data
              const lf = t?.landfall
              const err = lf && obs ? (parseUtc(lf.median_time).getTime() - parseUtc(obs.time).getTime()) / 3600e3 : null
              return (
                <tr key={ids[i]} className={`border-t hairline ${ids[i] === cycle ? 'text-amber' : ids[i] === compareB ? 'text-ion' : ''}`}>
                  <td className="py-1 num">{cycleLabel(ready[i].init)}</td>
                  <td className="num">{q.isLoading ? '…' : lf ? fmtUtc(lf.median_time) : 'no landfall'}</td>
                  <td className="text-right num">{lf ? pct(lf.fraction) : t ? '0%' : ''}</td>
                  {obs && <td className="text-right num">{err == null ? 'n/a' : signed(err, 'h', 1)}</td>}
                </tr>
              )
            })}
          </tbody>
        </table>
        {obs && <p className="mt-1 text-[10px] text-muted">Observed landfall {fmtUtc(obs.time)} (IBTrACS). Positive error: forecast later than observed.</p>}
      </section>
    </>
  )
}
