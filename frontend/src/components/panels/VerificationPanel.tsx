import { cycleLabel, fmtUtc, km, latlon, signed } from '../../format'
import { useSelection, useVerification } from '../../hooks'
import { useStore } from '../../store'
import { LineChart } from '../charts'
import { H, Loading, NotEvaluated, Problem, Stat } from '../ui'
import { RainVerification } from './RainVerification'

export function VerificationPanel() {
  const { event, cycle, eventId, tracks } = useSelection()
  const { hoverLead, set } = useStore()
  const v = useVerification(eventId, cycle)

  if (!eventId) return <NotEvaluated what="Verification" why="Select a historical replay. Verification compares forecast tracks with the observed IBTrACS best track." />
  if (eventId === 'current') return <NotEvaluated what="Verification of the latest run" why="A live forecast can only be verified after the event, once IBTrACS publishes the best track." />
  if (event.data && event.data.cycles_ready === 0) return <NotEvaluated what={`${event.data.name} forecast verification`} why="No ensemble forecast is loaded for this storm (TIGGE download pending). The observed track is real; nothing has been compared." />
  if (v.isLoading) return <Loading what="verification" />
  if (v.error) return <Problem error={v.error} />
  const d = v.data!
  const sum = event.data?.verification_summary

  return (
    <>
      <section>
        <H aside={`cycle ${cycleLabel(d.init)}`}>Track error by lead</H>
        {d.by_lead.length === 0 ? (
          <NotEvaluated what="No matched valid times" why="The forecast track and the best track do not overlap in time for this cycle." />
        ) : (
          <>
            <LineChart
              xLabel="lead (h)" yLabel="km" activeX={hoverLead}
              onHover={(x) => set({ hoverLead: x, ...(x != null ? { leadH: x } : {}) })}
              series={[
                { name: 'Ensemble-mean error', color: '#EF6B61', width: 2, points: d.by_lead.map((r) => ({ x: r.lead_h, y: r.mean_error_km })) },
                { name: 'Median member error', color: '#F3B85C', dashed: true, points: d.by_lead.map((r) => ({ x: r.lead_h, y: r.member_error_km_median })) },
                { name: 'Spread', color: '#66DCE7', points: d.by_lead.map((r) => ({ x: r.lead_h, y: r.spread_km })) },
              ]}
            />
            <p className="mt-1 text-[10px] text-muted">Hover the chart to move the map: red lines join the forecast mean to the observed position at each lead. Great-circle distances. {d.truth}.</p>
          </>
        )}
      </section>

      {d.landfall ? (
        <section>
          <H>Landfall verification</H>
          <div className="grid grid-cols-3 gap-3">
            <Stat label="Position error" value={km(d.landfall.position_error_km)} sub="mean landfall vs observed" />
            <Stat label="Timing error" value={signed(d.landfall.timing_error_h, 'h', 1)} sub="+ = forecast later" />
            <Stat label="Members" value={d.landfall.n_members_landfalling} sub={`of ${tracks.data?.n_members ?? '?'}`} />
          </div>
          <div className="mt-2 num text-[11px] text-muted">
            Forecast {latlon(d.landfall.forecast_mean.lat, d.landfall.forecast_mean.lon)} at {fmtUtc(d.landfall.forecast_mean.median_time)}; observed {latlon(d.landfall.observed.lat, d.landfall.observed.lon)} at {fmtUtc(d.landfall.observed.time)}.
          </div>
        </section>
      ) : (
        <NotEvaluated what="Landfall verification" why={event.data?.landfall ? 'No member of this cycle makes landfall within the tracked period.' : 'The storm did not make landfall according to IBTrACS.'} />
      )}

      {sum && (
        <section>
          <H aside={`${event.data?.verification_n_cycles} cycles`}>Event summary: mean-track error</H>
          <table className="w-full text-xs">
            <thead><tr className="label"><th className="py-1 text-left font-normal">Lead</th><th className="text-right font-normal">Error</th><th className="text-right font-normal">Spread</th><th className="text-right font-normal">n</th></tr></thead>
            <tbody>
              {sum.map((r) => (
                <tr key={r.lead_h} className="border-t hairline">
                  <td className="py-1 num">T+{r.lead_h}</td>
                  <td className="text-right num">{r.n ? km(r.mean_error_km) : 'Not yet evaluated'}</td>
                  <td className="text-right num">{r.n ? km(r.mean_spread_km) : ''}</td>
                  <td className="text-right num">{r.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-1 text-[10px] text-muted">Averaged over this event's cycles only: a case study, not a skill statistic. n is the number of cycles with a matched valid time.</p>
        </section>
      )}

      {cycle && <RainVerification eventId={eventId} cycle={cycle} event={event.data} />}
    </>
  )
}
