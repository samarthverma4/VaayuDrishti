import { addHours, cycleLabel, fmtDate, fmtIst, fmtUtc, km, latlon, pct } from '../../format'
import { nearestDistrict, useDistrictIndex } from '../../geoIndex'
import { useSelection, useSnapshots } from '../../hooks'
import { observedAt } from '../../map/data'
import { useStore } from '../../store'
import { LineChart } from '../charts'
import { H, Loading, ModeBadge, NotEvaluated, Problem, Seg, Stat } from '../ui'

export function EventPanel() {
  const { event, tracks, cycle, eventId } = useSelection()
  const { leadH, mode, member, set } = useStore()
  const idx = useDistrictIndex()

  if (eventId === 'current') return <CurrentHeader />
  if (event.isLoading) return <Loading what="event" />
  if (event.error) return <Problem error={event.error} />
  const e = event.data!
  const ready = e.cycles.filter((c) => c.status === 'ready')
  const t = tracks.data
  const mp = t?.mean.find((p) => p.lead_h === leadH)
  const obs = t ? observedAt(e.best_track, addHours(t.init, leadH)) : null
  const obsWind = t ? e.best_track.find((p) => +new Date(p.time + 'Z') === +addHours(t.init, leadH))?.wind_kt : null
  const lfNear = t?.landfall ? nearestDistrict(idx.data, t.landfall.mean_lat, t.landfall.mean_lon) : null
  const mem = member != null ? t?.members.find((m) => m.member === member) : undefined
  const at = (h: number) => t?.mean.find((p) => p.lead_h === h)

  return (
    <>
      <section>
        <div className="mb-1 flex items-center justify-between">
          <ModeBadge mode="historical-replay" />
          <span className="num text-[10px] text-muted">IBTrACS {e.sid}</span>
        </div>
        <h1 className="font-display text-2xl font-semibold">{e.name}</h1>
        <div className="num text-xs text-muted">{e.basin} · {fmtDate(e.start)} to {fmtDate(e.end)}</div>
        <div className="mt-3 grid grid-cols-3 gap-3">
          <Stat label="Observed peak" value={e.peak ? `${e.peak.wind_kt} kt` : 'n/a'} sub={e.peak?.category?.label} />
          <Stat label="Observed landfall" value={e.landfall ? fmtUtc(e.landfall.time).replace(' UTC', '') : 'none'} sub={e.landfall ? latlon(e.landfall.lat, e.landfall.lon) : 'stayed at sea'} />
          <Stat label="Cycles" value={`${ready.length}/${e.cycles.length}`} sub="00 UTC runs" />
        </div>
      </section>

      {ready.length === 0 ? (
        <section>
          <NotEvaluated
            what="No ensemble forecast loaded for this storm"
            why={`${e.cycles[0]?.reason ?? 'Forecast data missing.'} The observed best track is shown on the map. ECMWF's free open archive starts on 1 Apr 2024; ${e.name}'s forecasts are in the TIGGE archive (registered account, 48 h delay).`}
          />
          {!!e.snapshots?.length && <SnapshotCard eventId={e.id} />}
        </section>
      ) : !t ? (
        tracks.error ? <Problem error={tracks.error} title="No forecast track in this cycle" /> : <Loading what="ensemble tracks" />
      ) : (
        <>
          <section>
            <H aside={`cycle ${cycleLabel(t.init)}`}>What this cycle indicates</H>
            <p className="text-sm leading-relaxed">
              {t.members.filter((m) => m.points.length).length} of {t.n_members} members carry a closed low for {e.name} from the observed position.
              {at(24) && at(72) && <> Track spread grows from <span className="num">{km(at(24)!.spread_km)}</span> at T+24 to <span className="num">{km(at(72)!.spread_km)}</span> at T+72.</>}
              {t.landfall ? (
                <> {pct(t.landfall.fraction)} of members make landfall; the ensemble-mean landfall point is {lfNear ? <>near <b>{lfNear.district.name}, {lfNear.district.state}</b></> : latlon(t.landfall.mean_lat, t.landfall.mean_lon)} around <span className="num">{fmtUtc(t.landfall.median_time)}</span> (members span T+{Math.round(t.landfall.lead_h_p10)} to T+{Math.round(t.landfall.lead_h_p90)} h).</>
              ) : <> No member makes landfall within the tracked period.</>}
            </p>
          </section>

          <section>
            <H aside={<span className="num">T+{leadH} h</span>}>At the selected time</H>
            {mp ? (
              <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                <Stat label="Ensemble-mean position" value={latlon(mp.lat, mp.lon)} sub={`${mp.n_members} members alive`} />
                <Stat label="Spread (mean distance)" value={km(mp.spread_km)} sub={`80% of members within ${km(mp.radius80_km)}`} />
                <Stat label="Model 10 m wind (median)" value={`${Math.round(mp.vmax_kt.median)} kt`} sub={`10–90%: ${Math.round(mp.vmax_kt.p10)}–${Math.round(mp.vmax_kt.p90)} kt · model-derived`} />
                <Stat label="Central pressure (median)" value={`${Math.round(mp.msl_hpa.median)} hPa`} sub={`10–90%: ${Math.round(mp.msl_hpa.p10)}–${Math.round(mp.msl_hpa.p90)}`} />
                {obs && <Stat label="Observed position" value={latlon(obs.lat, obs.lon)} sub={`${obs.exact ? 'best-track fix' : 'interpolated'}${obsWind ? ` · ${obsWind} kt` : ''}`} />}
                {obs && <Stat label="Mean-track error now" value={km(Math.hypot((mp.lat - obs.lat) * 111.2, (mp.lon - obs.lon) * 111.2 * Math.cos((obs.lat * Math.PI) / 180)))} sub="great-circle approx." />}
              </div>
            ) : (
              <p className="text-sm text-muted">Fewer than 30% of members carry the storm at T+{leadH} h, so no ensemble mean is shown. Scrub the ribbon to the tracked span (teal band).</p>
            )}
            <p className="mt-2 text-[10px] leading-snug text-muted">Winds come from 0.25° fields and underestimate peak intensity; IMD categories are not assigned to model winds here.</p>
          </section>

          <section>
            <H aside="Ensemble Constellation">Uncertainty view</H>
            <Seg value={mode} onChange={(v) => set({ mode: v, member: v === 'members' ? member : null })} label="Constellation mode"
              options={[{ v: 'consensus', t: 'Consensus' }, { v: 'members', t: 'Members' }, { v: 'uncertainty', t: 'Uncertainty' }]} />
            <p className="mt-2 text-[11px] leading-snug text-muted">
              {mode === 'consensus' && 'Teal line: ensemble-mean track. Dashed region: ' + t.envelope_definition}
              {mode === 'members' && 'Each grey line is one member. Hover for its id and values; click to isolate. Amber dots: member landfall points.'}
              {mode === 'uncertainty' && 'Members and the 80% envelope together; the chart shows how spread grows with lead time.'}
            </p>
            {mode === 'members' && (
              <div className="mt-2">
                <div className="flex flex-wrap gap-1">
                  {t.members.map((m) => (
                    <button key={m.member} disabled={!m.points.length} onClick={() => set({ member: member === m.member ? null : m.member })}
                      className={`h-6 w-7 rounded-sm border num text-[10px] ${member === m.member ? 'border-ion text-ion' : 'hairline text-muted'} disabled:opacity-30`}
                      aria-pressed={member === m.member} aria-label={`Member ${m.member}`}>
                      {m.member}
                    </button>
                  ))}
                </div>
                {mem && (
                  <div className="mt-2 grid grid-cols-2 gap-3 rounded border hairline p-2">
                    <Stat label={`Member ${mem.member}${mem.member === 0 ? ' (control)' : ''}`} value={`${mem.points.length} steps`} sub={`to T+${mem.points.at(-1)?.lead_h ?? 0} h`} />
                    <Stat label="Deepest" value={`${Math.min(...mem.points.map((p) => p.msl_hpa)).toFixed(0)} hPa`} sub={`max ${Math.max(...mem.points.map((p) => p.vmax_kt)).toFixed(0)} kt`} />
                    <Stat label="Landfall" value={mem.landfall ? fmtUtc(mem.landfall.time) : 'none'} sub={mem.landfall ? latlon(mem.landfall.lat, mem.landfall.lon) : undefined} />
                  </div>
                )}
              </div>
            )}
            {mode === 'uncertainty' && (
              <div className="mt-3">
                <LineChart xLabel="lead (h)" yLabel="km" activeX={leadH} onHover={(x) => x != null && set({ leadH: x })}
                  series={[
                    { name: 'Mean distance to ensemble mean', color: '#66DCE7', points: t.mean.map((p) => ({ x: p.lead_h, y: p.spread_km })) },
                    { name: '80% radius', color: '#94A8B6', dashed: true, points: t.mean.map((p) => ({ x: p.lead_h, y: p.radius80_km })) },
                  ]} />
              </div>
            )}
          </section>

          {t.landfall && e.landfall && (
            <section>
              <H>Landfall: forecast vs observed</H>
              <div className="grid grid-cols-2 gap-3">
                <Stat label="Forecast (ensemble mean)" value={fmtUtc(t.landfall.median_time)} sub={`${latlon(t.landfall.mean_lat, t.landfall.mean_lon)} · ${t.landfall.n_members} members`} tone="text-teal" />
                <Stat label="Observed (IBTrACS)" value={fmtUtc(e.landfall.time)} sub={latlon(e.landfall.lat, e.landfall.lon)} />
              </div>
              <div className="mt-1 num text-[11px] text-muted">{fmtIst(t.landfall.median_time)} forecast · {fmtIst(e.landfall.time)} observed</div>
            </section>
          )}

          <section className="text-[11px] leading-relaxed text-muted">
            <H>Map key</H>
            <ul className="space-y-1">
              <li><span className="mr-1.5 inline-block h-0.5 w-5 align-middle bg-teal" />Ensemble-mean forecast track</li>
              <li><span className="mr-1.5 inline-block w-5 border-t border-dashed border-ink align-middle" />Observed best track (IBTrACS)</li>
              <li><span className="mr-1.5 inline-block w-5 border-t border-dashed border-ion align-middle" />80% member envelope (not a probability cone)</li>
              <li>● teal: forecast landfall · ● white: observed landfall · ○ white ring: observed position now</li>
            </ul>
            <p className="mt-2">{t.method}</p>
          </section>
        </>
      )}
      {cycle && <div className="num text-[10px] text-muted">Source: {t?.provenance.source ?? 'n/a'} · {t?.provenance.licence}</div>}
    </>
  )
}

/** One TIGGE control-forecast MSLP field at T+0, compared with the best track. Not a forecast. */
function SnapshotCard({ eventId }: { eventId: string }) {
  const q = useSnapshots(eventId, true)
  if (q.isLoading) return <Loading what="TIGGE snapshot" />
  if (q.error) return <Problem error={q.error} />
  return (
    <>
      {q.data!.snapshots.map((s) => (
        <div key={s.id} className="mt-4 rounded border hairline p-3" data-testid="tigge-snapshot">
          <H aside={<span className="num">{fmtUtc(s.valid_time)}</span>}>TIGGE snapshot</H>
          <p className="text-[11px] leading-snug text-muted">{s.kind}, {s.variable}. Isobars on the map; teal ring marks the model's pressure minimum.</p>
          <div className="mt-2 grid grid-cols-2 gap-3">
            <Stat label="Model MSLP minimum" value={`${s.model_min.msl_hpa.toFixed(1)} hPa`} sub={latlon(s.model_min.lat, s.model_min.lon)} tone="text-teal" />
            <Stat label="Observed (IBTrACS)" value={s.observed?.pres_hpa != null ? `${s.observed.pres_hpa} hPa` : 'n/a'}
              sub={s.observed ? `${latlon(s.observed.lat, s.observed.lon)}${s.observed.wind_kt != null ? ` · ${s.observed.wind_kt} kt` : ''}${s.observed.exact_fix ? '' : ' · interpolated'}` : 'outside best track'} />
            <Stat label="Position difference" value={km(s.distance_km)} sub="model low to best-track fix" />
            <Stat label="Field range" value={`${s.field_range_hpa[0]}–${s.field_range_hpa[1]} hPa`} sub={`${s.coverage.lat[0]}–${s.coverage.lat[1]}°N, ${s.coverage.lon[0]}–${s.coverage.lon[1]}°E`} />
          </div>
          <p className="mt-2 text-[11px] leading-snug">{s.not_available}</p>
          <details className="mt-2 text-[10px] text-muted">
            <summary className="cursor-pointer">Provenance</summary>
            <div className="num mt-1 space-y-0.5 break-all">
              <div>{s.provenance.source} · {s.provenance.licence}</div>
              <div>{s.provenance.file} ({(s.provenance.bytes / 1024).toFixed(1)} KB, downloaded {fmtUtc(s.provenance.downloaded_at)})</div>
              <div>sha256 {s.provenance.sha256}</div>
              <div>GRIB: centre {String(s.provenance.grib.centre)}, class {String(s.provenance.grib.marsClass)}, stream {String(s.provenance.grib.marsStream)}, type {String(s.provenance.grib.marsType)}, grid {String(s.provenance.grib.gridType)} N{String(s.provenance.grib.N)}, {String(s.provenance.grib.numberOfDataPoints)} points</div>
              <div>{s.isobar_note}</div>
            </div>
          </details>
        </div>
      ))}
    </>
  )
}

function CurrentHeader() {
  const { index, tracks, cycle } = useSelection()
  const { leadH } = useStore()
  const cur = index.data?.current
  if (!cur) return <Loading what="current run" />
  const sys = cur.systems.find((s) => s.id === cycle)
  const t = tracks.data
  const mp = t?.mean.find((p) => p.lead_h === leadH)
  return (
    <>
      <section>
        <ModeBadge mode="current-forecast" />
        <h1 className="mt-1 font-display text-2xl font-semibold">Latest ECMWF run</h1>
        <div className="num text-xs text-muted">Init {fmtUtc(cur.init)} · {fmtIst(cur.init)} · {cur.members} members</div>
        <p className="mt-2 text-sm leading-relaxed">
          {sys
            ? <>A closed low appears in the ensemble mean from T+{sys.first_lead_h} h near {latlon(sys.first_lat, sys.first_lon)}. {sys.members_tracked} of {sys.members} members carry it. This is a model feature, not an observed or named cyclone.</>
            : <>Showing rainfall guidance for all of India. Choose a system in the top bar to see tracks.</>}
        </p>
      </section>
      {t && (
        <section>
          <H aside={<span className="num">T+{leadH} h</span>}>At the selected time</H>
          {mp ? (
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Ensemble-mean position" value={latlon(mp.lat, mp.lon)} sub={`${mp.n_members} members`} />
              <Stat label="Spread" value={km(mp.spread_km)} sub={`80% within ${km(mp.radius80_km)}`} />
              <Stat label="Central pressure (median)" value={`${Math.round(mp.msl_hpa.median)} hPa`} sub={`10–90%: ${Math.round(mp.msl_hpa.p10)}–${Math.round(mp.msl_hpa.p90)}`} />
              <Stat label="Model 10 m wind (median)" value={`${Math.round(mp.vmax_kt.median)} kt`} sub="model-derived" />
            </div>
          ) : <p className="text-sm text-muted">Too few members carry the system at this lead.</p>}
          {t.landfall && <p className="mt-2 text-sm">{pct(t.landfall.fraction)} of members bring it ashore; median landfall {fmtUtc(t.landfall.median_time)}.</p>}
        </section>
      )}
      <NotEvaluated what="Verification" why="This is a live forecast; it can only be verified after the event, against IBTrACS." />
    </>
  )
}
