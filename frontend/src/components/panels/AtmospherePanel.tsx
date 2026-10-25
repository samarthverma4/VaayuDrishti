import { useQuery } from '@tanstack/react-query'
import { api } from '../../api'
import { fmtDate, fmtUtc, HAZARD_LABEL, latlon } from '../../format'
import { useIndex } from '../../hooks'
import { useStore } from '../../store'
import { H, Loading, ModeBadge, Problem, Prob } from '../ui'

export function AtmospherePanel() {
  const index = useIndex()
  const { selectEvent, set } = useStore()
  const cur = index.data?.current
  const domain = useQuery({ queryKey: ['districts', 'current', 'domain'], queryFn: () => api.districts('current', 'domain'), enabled: !!cur })

  if (index.isLoading) return <Loading what="the atmosphere" />
  if (index.error) return <Problem error={index.error} />

  const top = (domain.data?.rows ?? [])
    .map((r) => ({ r, p: Math.max(...r.p_rain.very_heavy), w: r.p_rain.very_heavy.indexOf(Math.max(...r.p_rain.very_heavy)) }))
    .filter((x) => x.p > 0)
    .sort((a, b) => b.p - a.p)
    .slice(0, 8)

  return (
    <>
      <section>
        <H aside="Overview">Atmospheric Signals</H>
        <p className="text-sm leading-relaxed text-muted">
          VYOMTRA turns ECMWF ensemble forecasts into tracks, probabilities and district exposure. Select a cyclone on the map
          or in the list to replay how its forecast evolved, or open the latest run.
        </p>
      </section>

      {cur ? (
        <section>
          <H aside={<ModeBadge mode="current-forecast" />}>Latest run</H>
          <div className="num text-xs text-muted">Init {fmtUtc(cur.init)} · {cur.members} members · retrieved {cur.retrieved_at ? fmtUtc(cur.retrieved_at) : 'n/a'}</div>
          {cur.systems.length === 0 ? (
            <p className="mt-2 text-sm">No closed low over the North Indian Ocean in the ensemble mean for the next 10 days.</p>
          ) : (
            <ul className="mt-2 space-y-1.5">
              {cur.systems.map((s) => (
                <li key={s.id}>
                  <button onClick={() => { selectEvent('current', s.id); set({ section: 'events' }) }}
                    className="w-full rounded border hairline px-2.5 py-2 text-left text-sm hover:border-ion">
                    <span className="font-medium capitalize">{s.id.replace('-', ' ')}</span>
                    <span className="ml-2 num text-xs text-muted">first at T+{s.first_lead_h} h · {latlon(s.first_lat, s.first_lon)} · {s.members_tracked}/{s.members} members tracked</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-[11px] leading-snug text-muted">{cur.detection}. A closed low is a model feature, not a named cyclone.</p>

          <div className="mt-4">
            <div className="label mb-1">Highest district probabilities · {HAZARD_LABEL.very_heavy}</div>
            {domain.isLoading && <Loading what="district signals" />}
            {domain.data && top.length === 0 && <p className="text-sm text-muted">No district reaches this threshold in any member.</p>}
            <table className="w-full text-sm">
              <tbody>
                {top.map(({ r, p, w }) => (
                  <tr key={r.id} className="border-b hairline last:border-0">
                    <td className="py-1"><button className="text-left hover:text-ion" onClick={() => { selectEvent('current', 'domain'); set({ section: 'districts', districtId: r.id, hazard: 'very_heavy' }) }}>{r.name}<span className="text-muted">, {r.state}</span></button></td>
                    <td className="py-1 text-right num text-xs text-muted">{domain.data && fmtDate(domain.data.windows[w].valid_end)}</td>
                    <td className="w-14 py-1 text-right"><Prob p={p} compact /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <Problem error={null} title="No current run processed. Run: python -m pipeline.fetch --latest && python -m pipeline.build --current" />
      )}

      <section>
        <H aside={`${index.data?.events.length ?? 0} events`}>Historical replays</H>
        <ul className="space-y-1">
          {index.data?.events.map((e) => (
            <li key={e.id}>
              <button onClick={() => { selectEvent(e.id); set({ section: 'events' }) }} className="flex w-full items-baseline justify-between rounded px-1 py-1 text-left text-sm hover:bg-slate">
                <span>{e.name} <span className="text-muted">· {e.basin}</span></span>
                <span className="num text-xs text-muted">{e.cycles_ready ? `${e.cycles_ready} cycles` : 'best track only'}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="text-[11px] leading-relaxed text-muted">
        <H>How to read VYOMTRA</H>
        <p><b className="text-ink">Probability</b> is the fraction of ensemble members meeting a stated condition. <b className="text-ink">Spread</b> is how far members sit from the ensemble mean. <b className="text-ink">Severity</b> is shown in physical units. They are never merged into one score.</p>
      </section>
    </>
  )
}
