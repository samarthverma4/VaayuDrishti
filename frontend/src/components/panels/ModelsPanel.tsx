import { ExternalLink } from 'lucide-react'
import { fmtUtc } from '../../format'
import { useSelection, useSources } from '../../hooks'
import { H, Loading, NotEvaluated, Problem, Stat } from '../ui'

export function ModelsPanel() {
  const sources = useSources()
  const { fields } = useSelection()
  const prov = fields.data?.provenance
  return (
    <>
      <section>
        <H>Model Observatory</H>
        {prov ? (
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Model in view" value={prov.model} sub={prov.source} />
            <Stat label="Members loaded" value={prov.members} sub={`grid ${prov.grid_deg}°`} />
            <Stat label="Initialised" value={fmtUtc(prov.init_time)} sub={prov.init_time_ist} />
            <Stat label="Leads" value={`T+${prov.leads_h[0]} to T+${prov.leads_h[1]} h`} sub="3-hourly to 144, then 6-hourly" />
            <Stat label="Retrieved" value={prov.retrieved_at ? fmtUtc(prov.retrieved_at) : 'n/a'} sub={prov.licence ?? undefined} />
          </div>
        ) : <p className="text-sm text-muted">Select an event to see the model behind it.</p>}
      </section>

      <NotEvaluated what="Multi-model comparison and Atmospheric Fingerprint"
        why="Only one ensemble (ECMWF IFS ENS) is loaded. Comparing NEPS-G, IMD GEFS or AIFS ENS needs their data (TIGGE account; AIFS from the open-data feed), so no comparison is drawn." />

      <section>
        <H aside="data/sources.yaml">Source registry</H>
        {sources.isLoading && <Loading what="sources" />}
        {sources.error && <Problem error={sources.error} />}
        <div className="space-y-2">
          {sources.data?.sources.map((s) => (
            <article key={s.id} className="rounded border hairline p-2.5 text-xs">
              <div className="flex items-start justify-between gap-2">
                <div className="font-medium">{s.name}</div>
                <span className={`shrink-0 rounded-sm border px-1 font-mono text-[9px] uppercase ${s.status === 'in use' ? 'border-teal/70 text-teal' : 'hairline text-muted'}`}>{s.status}</span>
              </div>
              <div className="mt-1 text-muted">{s.role}</div>
              <dl className="mt-1.5 grid grid-cols-[84px_1fr] gap-x-2 gap-y-0.5 text-[11px]">
                <dt className="text-muted">Grid</dt><dd>{s.grid}</dd>
                <dt className="text-muted">Members</dt><dd>{String(s.members)}</dd>
                <dt className="text-muted">Archive</dt><dd>from {s.archive_start} · {s.latency}</dd>
                <dt className="text-muted">Licence</dt><dd>{s.licence}</dd>
                <dt className="text-muted">Verified</dt><dd>{s.verified_on ?? 'unverified'} · {s.verified_by}</dd>
              </dl>
              <a href={s.url} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-[11px] text-ion hover:underline">Source <ExternalLink size={10} /></a>
            </article>
          ))}
        </div>
      </section>
    </>
  )
}
