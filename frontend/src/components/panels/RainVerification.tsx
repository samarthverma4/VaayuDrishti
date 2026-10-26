import { useState } from 'react'
import type { EventDetail, RainScores } from '../../api'
import { cycleLabel, fmtDate } from '../../format'
import { useRainVerification } from '../../hooks'
import { LineChart } from '../charts'
import { H, Loading, NotEvaluated, Problem, Seg, Stat } from '../ui'

type Thr = 'heavy' | 'very_heavy' | 'extremely_heavy'
const THR: { v: Thr; t: string }[] = [{ v: 'heavy', t: '≥ 64.5' }, { v: 'very_heavy', t: '≥ 115.6' }, { v: 'extremely_heavy', t: '≥ 204.5' }]
const f2 = (v: number | null | undefined) => (v == null ? '–' : v.toFixed(2))

/** Ensemble rainfall against IMD gridded rainfall: per day for the selected cycle, and pooled by lead day. */
export function RainVerification({ eventId, cycle, event }: { eventId: string; cycle: string; event?: EventDetail }) {
  const q = useRainVerification(eventId, cycle)
  const [thr, setThr] = useState<Thr>('heavy')
  const sum = event?.rain_verification_summary

  return (
    <>
      <section data-testid="rain-verification">
        <H aside={q.data ? `cycle ${cycleLabel(q.data.init)}` : undefined}>Rainfall vs IMD observations</H>
        <Seg value={thr} onChange={setThr} label="Rain threshold (mm per 24 h)" options={THR} />
        {q.isLoading ? <Loading what="rainfall verification" /> : q.error ? (
          (q.error as { status?: number }).status === 404
            ? <NotEvaluated what="No IMD day scored for this cycle" why="Either the IMD file for these dates is not downloaded, or the storm stayed at sea (fewer than 20 IMD land cells within 300 km) on every day this cycle can be compared." />
            : <Problem error={q.error} />
        ) : (() => {
          const d = q.data!
          return (
            <>
              <div className="mt-2 overflow-x-auto">
                <table className="w-full text-xs">
                  <thead><tr className="label">
                    <th className="py-1 text-left font-normal">IMD day</th><th className="text-right font-normal">Day</th>
                    <th className="text-right font-normal" title="mean over scored cells, observed / ensemble mean">Mean obs/fc</th>
                    <th className="text-right font-normal">MAE</th><th className="text-right font-normal">POD</th>
                    <th className="text-right font-normal">FAR</th><th className="text-right font-normal">CSI</th>
                    <th className="text-right font-normal" title={`Fractions Skill Score, ${d.fss_scales_cells.at(-1)} x ${d.fss_scales_cells.at(-1)} cells`}>FSS</th>
                  </tr></thead>
                  <tbody>
                    {d.days.map((r) => {
                      const s = r.thresholds[thr]
                      return (
                        <tr key={r.date} className="border-t hairline num" title={`${r.n_cells} cells · observed ${s.observed_cells}, forecast ${s.forecast_cells} cells at the threshold · hits ${s.hits}, misses ${s.misses}, false alarms ${s.false_alarms} · Brier ${s.brier}`}>
                          <td className="py-1">{fmtDate(r.date)}</td>
                          <td className="text-right">{r.lead_day}</td>
                          <td className="text-right">{r.obs_mean_mm.toFixed(0)}/{r.fc_mean_mm.toFixed(0)}</td>
                          <td className="text-right">{r.mae_mm.toFixed(0)}</td>
                          <td className="text-right">{f2(s.pod)}</td>
                          <td className="text-right">{f2(s.far)}</td>
                          <td className="text-right">{f2(s.csi)}</td>
                          <td className="text-right">{f2(s.fss[String(d.fss_scales_cells.at(-1))])}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              {d.days.length > 0 && (() => {
                const top = d.days.reduce((a, b) => (b.obs_max_mm > a.obs_max_mm ? b : a))
                return (
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <Stat label={`Wettest IMD cell (${fmtDate(top.date)})`} value={`${top.obs_max_mm.toFixed(0)} mm`} sub={`ensemble-mean max ${top.fc_mean_max_mm.toFixed(0)} mm`} />
                    <Stat label="Cells scored that day" value={top.n_cells} sub={`${top.thresholds[thr].observed_cells} observed at the threshold`} />
                  </div>
                )
              })()}
              <p className="mt-2 text-[10px] leading-snug text-muted">
                mm per 24 h. {d.area}. {d.yes_rule[0].toUpperCase() + d.yes_rule.slice(1)}. Day 1 is the first full IMD day after the run starts.
                Hover a row for counts and the Brier score. Truth: {d.truth}.
                {d.observations.some((o) => o.status?.startsWith('binary download only')) && <> <span className="text-amber">This year's IMD grid is a binary download not yet in IMD's published 1901–2024 archive; it may be revised.</span></>}
              </p>
              {d.skipped.length > 0 && (
                <details className="mt-1 text-[10px] text-muted">
                  <summary className="cursor-pointer">{d.skipped.length} day{d.skipped.length > 1 ? 's' : ''} not scored</summary>
                  <ul className="mt-1 space-y-0.5">{d.skipped.map((s) => <li key={s.date}><span className="num">{s.date}</span>: {s.reason}</li>)}</ul>
                </details>
              )}
              <details className="mt-1 text-[10px] text-muted">
                <summary className="cursor-pointer">Observation provenance</summary>
                {d.observations.map((p) => (
                  <div key={p.file} className="num mt-1 break-all">{p.file} · {p.status} · {(p.bytes / 1e6).toFixed(1)} MB · sha256 {p.sha256} · {p.url}</div>
                ))}
              </details>
            </>
          )
        })()}
      </section>

      {sum && (
        <section>
          <H aside={`${event?.rain_verification_n_cycles} cycles`}>Event summary: rainfall by lead day</H>
          <LineChart xLabel="lead day" yLabel="score" xTicks={sum.map((r) => r.lead_day)} format={(v) => v.toFixed(1)}
            series={[
              { name: 'POD', color: '#66DCE7', width: 2, points: sum.map((r) => ({ x: r.lead_day, y: r.thresholds[thr].pod })) },
              { name: 'CSI', color: '#EF6B61', width: 2, points: sum.map((r) => ({ x: r.lead_day, y: r.thresholds[thr].csi })) },
              { name: 'FAR', color: '#F3B85C', dashed: true, points: sum.map((r) => ({ x: r.lead_day, y: r.thresholds[thr].far })) },
            ]} />
          <table className="mt-2 w-full text-xs">
            <thead><tr className="label"><th className="py-1 text-left font-normal">Lead day</th><th className="text-right font-normal">MAE</th><th className="text-right font-normal">Bias</th><th className="text-right font-normal">Hits/miss/FA</th><th className="text-right font-normal">n days</th></tr></thead>
            <tbody>
              {sum.map((r) => {
                const s: RainScores = r.thresholds[thr]
                return (
                  <tr key={r.lead_day} className="border-t hairline num">
                    <td className="py-1">{r.lead_day}</td>
                    <td className="text-right">{r.mae_mm.toFixed(0)} mm</td>
                    <td className="text-right">{r.bias_mm > 0 ? '+' : ''}{r.bias_mm.toFixed(0)} mm</td>
                    <td className="text-right">{s.hits}/{s.misses}/{s.false_alarms}</td>
                    <td className="text-right">{r.n_days}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="mt-1 text-[10px] text-muted">Contingency counts pooled over this event's cycles; MAE and bias averaged over days. A case study, not a skill statistic.</p>
        </section>
      )}
    </>
  )
}
