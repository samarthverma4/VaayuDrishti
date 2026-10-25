import { useMutation } from '@tanstack/react-query'
import { Download, FileCode2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { api, ApiError, type Hazard } from '../../api'
import { fmtDate, fmtUtc, HAZARD_LABEL, pct } from '../../format'
import { useDistricts, useSelection } from '../../hooks'
import { H, Loading, NotEvaluated, Problem, Seg } from '../ui'

function save(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

export function DataPanel() {
  const { eventId, cycle, tracks } = useSelection()
  const table = useDistricts(eventId, cycle)
  const [hazard, setHazard] = useState<Hazard>('very_heavy')
  const [win, setWin] = useState(0)
  const [picked, setPicked] = useState<string[]>([])
  const draft = useMutation({ mutationFn: api.draftAdvisory })

  const candidates = useMemo(() => {
    if (!table.data) return []
    return table.data.rows
      .map((r) => ({ r, p: (hazard === 'strike' ? r.p_strike?.[win] : r.p_rain[hazard][win]) ?? 0 }))
      .filter((x) => x.p > 0)
      .sort((a, b) => b.p - a.p)
      .slice(0, 25)
  }, [table.data, hazard, win])

  const exportTracks = () => {
    const t = tracks.data!
    const fc = {
      type: 'FeatureCollection',
      properties: { init: t.init, provenance: t.provenance, disclaimer: 'Experimental decision-support guidance. Not an official IMD warning.' },
      features: [
        { type: 'Feature', properties: { kind: 'ensemble-mean', points: t.mean }, geometry: { type: 'LineString', coordinates: t.mean.map((p) => [p.lon, p.lat]) } },
        ...t.members.filter((m) => m.points.length > 1).map((m) => ({ type: 'Feature', properties: { kind: 'member', member: m.member, leads_h: m.points.map((p) => p.lead_h), landfall: m.landfall }, geometry: { type: 'LineString', coordinates: m.points.map((p) => [p.lon, p.lat]) } })),
        ...(t.envelope ? [{ type: 'Feature', properties: { kind: 'envelope', definition: t.envelope_definition }, geometry: t.envelope }] : []),
      ],
    }
    save(`vyomtra-${eventId}-${cycle}-tracks.geojson`, JSON.stringify(fc), 'application/geo+json')
  }
  const exportDistricts = () => {
    const d = table.data!
    const head = ['district_id', 'district', 'state', 'window_start_utc', 'window_end_utc', 'p_heavy', 'p_very_heavy', 'p_extremely_heavy', 'p_track_120km', 'rain_p10_mm', 'rain_p50_mm', 'rain_p90_mm']
    const lines = [head.join(',')]
    for (const r of d.rows) for (const w of d.windows)
      lines.push([r.id, `"${r.name}"`, `"${r.state}"`, w.valid_start, w.valid_end, r.p_rain.heavy[w.index], r.p_rain.very_heavy[w.index], r.p_rain.extremely_heavy[w.index], r.p_strike?.[w.index] ?? '', r.rain_mm.p10[w.index], r.rain_mm.p50[w.index], r.rain_mm.p90[w.index]].join(','))
    save(`vyomtra-${eventId}-${cycle}-districts.csv`, lines.join('\n'), 'text/csv')
  }

  return (
    <>
      <section>
        <H aside="CAP 1.2 · Draft">Advisory draft</H>
        <div className="rounded border border-amber/60 px-2.5 py-2 text-xs text-amber">Experimental Decision-Support Guidance. Not an Official IMD Warning. Drafts are for an authorized forecaster; VYOMTRA never sends alerts.</div>
        {!eventId || !cycle ? (
          <p className="mt-2 text-sm text-muted">Select an event and cycle first.</p>
        ) : table.isLoading ? <Loading what="districts" /> : table.error ? <Problem error={table.error} /> : (
          <div className="mt-3 space-y-3">
            <Seg value={hazard} onChange={(v) => { setHazard(v); setPicked([]) }} label="Hazard"
              options={[{ v: 'heavy', t: '≥64.5' }, { v: 'very_heavy', t: '≥115.6' }, { v: 'extremely_heavy', t: '≥204.5' }, { v: 'strike', t: 'Track' }]} />
            <label className="block text-xs">
              <span className="label">Valid window</span>
              <select value={win} onChange={(e) => { setWin(Number(e.target.value)); setPicked([]) }} className="mt-1 w-full rounded border hairline bg-slate px-1.5 py-1 num">
                {table.data!.windows.map((w) => <option key={w.index} value={w.index}>D{w.index + 1}: {fmtUtc(w.valid_start)} → {fmtUtc(w.valid_end)}</option>)}
              </select>
            </label>
            <fieldset>
              <legend className="label mb-1">Districts with a signal ({HAZARD_LABEL[hazard]})</legend>
              {candidates.length === 0 && <p className="text-sm text-muted">No district has a non-zero probability for this hazard and window.</p>}
              <div className="max-h-44 space-y-0.5 overflow-y-auto scroll-thin">
                {candidates.map(({ r, p }) => (
                  <label key={r.id} className="flex cursor-pointer items-center gap-2 text-xs">
                    <input type="checkbox" className="accent-[#66DCE7]" checked={picked.includes(r.id)}
                      onChange={(e) => setPicked(e.target.checked ? [...picked, r.id] : picked.filter((x) => x !== r.id))} />
                    <span className="flex-1">{r.name}<span className="text-muted">, {r.state}</span></span>
                    <span className="num">{pct(p)}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <button disabled={!picked.length || draft.isPending}
              onClick={() => draft.mutate({ event_id: eventId, cycle, hazard, window: win, district_ids: picked })}
              className="w-full rounded border border-ion/70 bg-slate py-1.5 text-sm text-ion disabled:opacity-40">
              {draft.isPending ? 'Generating…' : `Generate draft for ${picked.length} district${picked.length === 1 ? '' : 's'}`}
            </button>
            {draft.error && <Problem error={draft.error instanceof ApiError ? draft.error : new Error(String(draft.error))} />}
            {draft.data && (
              <div className="space-y-2">
                <div className={`text-xs ${draft.data.validation.valid ? 'text-teal' : 'text-coral'}`}>
                  {draft.data.validation.valid ? `Valid against ${draft.data.validation.schema}` : `Schema errors: ${draft.data.validation.errors.join('; ')}`}
                  <span className="ml-1 num text-muted">{draft.data.validation.identifier}</span>
                </div>
                <pre className="max-h-56 overflow-auto rounded border hairline bg-abyss p-2 text-[10px] leading-snug scroll-thin">{draft.data.cap_xml}</pre>
                <div className="flex gap-2">
                  <button onClick={() => save(`${draft.data!.validation.identifier}.xml`, draft.data!.cap_xml, 'application/xml')} className="flex items-center gap-1 rounded border hairline px-2 py-1 text-xs hover:border-ion"><FileCode2 size={12} /> CAP XML</button>
                  <button onClick={() => save(`${draft.data!.validation.identifier}.json`, JSON.stringify(draft.data, null, 2), 'application/json')} className="flex items-center gap-1 rounded border hairline px-2 py-1 text-xs hover:border-ion"><Download size={12} /> JSON</button>
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      <section>
        <H>Data exports</H>
        {!eventId || !cycle ? <p className="text-sm text-muted">Select an event and cycle to export its data.</p> : (
          <div className="flex flex-wrap gap-2">
            <button disabled={!tracks.data} onClick={exportTracks} className="flex items-center gap-1 rounded border hairline px-2 py-1 text-xs hover:border-ion disabled:opacity-40"><Download size={12} /> Tracks GeoJSON</button>
            <button disabled={!table.data} onClick={exportDistricts} className="flex items-center gap-1 rounded border hairline px-2 py-1 text-xs hover:border-ion disabled:opacity-40"><Download size={12} /> District table CSV</button>
            <a href="/api/v1/docs" target="_blank" rel="noreferrer" className="flex items-center gap-1 rounded border hairline px-2 py-1 text-xs hover:border-ion">API docs</a>
          </div>
        )}
        {cycle && tracks.data && <p className="mt-2 text-[10px] text-muted">Exports carry provenance: {tracks.data.provenance.source}, init {fmtDate(tracks.data.init)}, {tracks.data.provenance.licence}.</p>}
      </section>

      <NotEvaluated what="Validated public dissemination" why="Out of scope by design: VYOMTRA produces drafts only and has no SACHET or public alert integration." />
    </>
  )
}
