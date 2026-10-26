// Typed client for the VaayuDrishti API. Every number shown in the UI comes from these responses.

export type Category = { code: string; label: string } | null

export interface Provenance {
  source_id: string
  source: string
  licence: string | null
  model: string
  init_time: string
  init_time_ist: string
  members: number
  grid_deg: number
  leads_h: [number, number]
  lead_steps_h?: number[]
  retrieved_at: string | null
  mode: 'historical-replay' | 'current-forecast'
  generated_at: string
}

export interface CycleInfo {
  init: string
  init_ist: string
  status: 'ready' | 'missing'
  reason?: string
  members?: number
  leads_h?: [number, number]
  has_tracks?: boolean
  has_rain_verification?: boolean
  members_tracked?: number
}

export interface Landfall { time: string; lat: number; lon: number }

export interface EventSummary {
  id: string
  sid: string
  name: string
  basin: string
  hazard: 'cyclone'
  mode: 'historical-replay'
  ensemble_source: 'ecmwf-ifs-ens' | 'tigge'
  start: string
  end: string
  landfall: Landfall | null
  bbox: { lat_min: number; lat_max: number; lon_min: number; lon_max: number }
  peak: { wind_kt: number; time: string; category: Category } | null
  cycles: CycleInfo[]
  cycles_ready: number
  best_track_source: string
  snapshots?: { id: string; valid_time: string; kind: string; model_min: Snapshot['model_min']; distance_km: number | null }[]
  thumbnail: [number, number][]
}

export interface BestTrackPoint {
  time: string
  time_ist: string
  lat: number
  lon: number
  wind_kt: number | null
  pres_hpa: number | null
  category: Category
}

export interface LeadSummary { lead_h: number; n: number; mean_error_km: number | null; mean_spread_km: number | null }

export interface Snapshot {
  id: string; valid_time: string; valid_time_ist: string; kind: string; variable: string
  model_min: { lat: number; lon: number; msl_hpa: number }
  field_range_hpa: [number, number]
  coverage: { lat: [number, number]; lon: [number, number] }
  observed: null | { lat: number; lon: number; wind_kt: number | null; pres_hpa: number | null; exact_fix: boolean }
  distance_km: number | null
  isobars: GeoJSON.FeatureCollection
  isobar_note: string
  provenance: { file: string; sha256: string; bytes: number; downloaded_at: string; source: string; licence: string; grib: Record<string, string | number | null> }
  not_available: string
}

export interface EventDetail extends EventSummary {
  best_track: BestTrackPoint[]
  verification_summary: LeadSummary[] | null
  verification_n_cycles: number
  rain_verification_summary?: RainLeadSummary[] | null
  rain_verification_n_cycles?: number
}

export interface CurrentSystem extends CycleInfo { id: string; first_lead_h: number; first_lat: number; first_lon: number }

export interface CurrentSummary {
  init: string
  init_ist: string
  retrieved_at: string | null
  domain: { lat_min: number; lat_max: number; lon_min: number; lon_max: number }
  systems: CurrentSystem[]
  members: number
  detection: string
}

export interface Source {
  id: string; name: string; institution: string; role: string; grid: string; members: string | number
  horizon: string; cycles: string; archive_start: string; latency: string; licence: string; access: string
  variables_used: string; status: string; verified_by: string; verified_on: string | null; url: string
}

export interface TrackPoint { lead_h: number; lat: number; lon: number; msl_hpa: number; depth_hpa: number; vmax_kt: number }
export interface MemberLandfall { lat: number; lon: number; lead_h: number; time: string; vmax_kt: number }
export interface MeanPoint {
  lead_h: number; valid_time: string; lat: number; lon: number; n_members: number
  spread_km: number; radius80_km: number
  vmax_kt: { p10: number; median: number; p90: number }
  msl_hpa: { p10: number; median: number; p90: number }
  category_median: Category
}
export interface Tracks {
  init: string
  n_members: number
  members: { member: number; points: TrackPoint[]; landfall: MemberLandfall | null }[]
  mean: MeanPoint[]
  envelope: GeoJSON.Geometry | null
  envelope_definition: string
  landfall: null | {
    n_members: number; fraction: number; mean_lat: number; mean_lon: number
    median_lead_h: number; lead_h_p10: number; lead_h_p90: number; median_time: string
  }
  method: string
  provenance: Provenance
}

export interface Window { index: number; start_h: number; end_h: number; valid_start: string; valid_end: string }
export type LayerKey = 'strike' | 'p_heavy' | 'p_very_heavy' | 'p_extremely_heavy' | 'rain_mean' | 'efi' | 'sot'
export interface Fields {
  bounds: [number, number][]
  windows: Window[]
  layers: Partial<Record<LayerKey, string[]>>
  legends: Partial<Record<'prob' | 'rain' | 'efi' | 'sot', { kind: string; units: string; stops: { value: number; rgba: number[] }[] }>>
  climate?: { source: string; licence: string; years: [number, number]; half_window_days: number } | null
  definitions: Record<string, string>
  provenance: Provenance
}

export type Hazard = 'heavy' | 'very_heavy' | 'extremely_heavy' | 'strike'
export interface DistrictRow {
  id: string; name: string; state: string
  p_strike: number[] | null
  p_rain: Record<'heavy' | 'very_heavy' | 'extremely_heavy', number[]>
  rain_mm: Record<'p10' | 'p50' | 'p90', number[]>
  efi_max?: number[]
  p?: number
}
export interface Districts { windows: Window[]; rows: DistrictRow[]; definitions: Record<string, string>; provenance: Provenance }

export interface RainScores { hits: number; misses: number; false_alarms: number; pod: number | null; far: number | null; csi: number | null }
export interface RainDay {
  date: string; start_h: number; end_h: number; lead_day: number; valid_start: string; valid_end: string
  n_cells: number; obs_mean_mm: number; fc_mean_mm: number; obs_max_mm: number; fc_mean_max_mm: number; bias_mm: number; mae_mm: number
  thresholds: Record<string, RainScores & { threshold_mm: number; observed_cells: number; forecast_cells: number; brier: number; fss: Record<string, number | null> }>
}
export interface RainVerification {
  init: string; days: RainDay[]; skipped: { date: string; reason: string }[]
  truth: string; area: string; yes_rule: string; fss_scales_cells: number[]; cell_deg: number
  observations: { file: string; sha256: string; bytes: number; downloaded_at: string; source: string; url: string; status?: string }[]
}
export interface RainLeadSummary { lead_day: number; n_days: number; mae_mm: number; bias_mm: number; thresholds: Record<string, RainScores> }

export interface VerificationLead {
  lead_h: number; valid_time: string; obs_lat: number; obs_lon: number; obs_wind_kt: number | null
  mean_error_km: number; member_error_km_median: number | null; spread_km: number; n_members: number
}
export interface Verification {
  init: string
  by_lead: VerificationLead[]
  landfall: null | {
    observed: Landfall
    forecast_mean: { lat: number; lon: number; median_time: string }
    position_error_km: number; timing_error_h: number; n_members_landfalling: number; sign_convention: string
  }
  truth: string
}

export interface Comparison {
  cycle_a: string; cycle_b: string; matched_valid_times: number
  by_valid_time: { valid_time: string; lead_a_h: number; lead_b_h: number; displacement_km: number; spread_change_km: number; a: { lat: number; lon: number }; b: { lat: number; lon: number } }[]
  landfall: null | { shift_km: number; time_change_h: number; fraction_change: number }
  districts: null | { threshold: string; p_min: number; added: string[]; removed: string[]; kept: string[] }
  note: string
}

export interface DistrictMeta { id: string; name: string; state: string; bbox: [number, number, number, number]; centroid: [number, number] }

export interface ApiProblem { missing: string; why: string; available: string | null }

export class ApiError extends Error {
  status: number
  problem: ApiProblem | null
  constructor(status: number, problem: ApiProblem | null, fallback: string) {
    super(problem ? `${problem.missing}: ${problem.why}` : fallback)
    this.status = status
    this.problem = problem
  }
}

const BASE = '/api/v1'

async function get<T>(path: string): Promise<T> {
  let res: Response
  try {
    res = await fetch(BASE + path)
  } catch {
    throw new ApiError(0, { missing: 'API connection', why: 'The VaayuDrishti API is not reachable. Start it with: uvicorn backend.app.main:app --port 8000', available: null }, 'offline')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new ApiError(res.status, body?.detail && typeof body.detail === 'object' ? body.detail : null, `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const cycleId = (iso: string) => iso.slice(0, 13).replace(/[-T:]/g, '')

export const api = {
  events: () => get<{ generated_at: string; events: EventSummary[]; current: CurrentSummary | null }>('/events'),
  event: (id: string) => get<EventDetail>(`/events/${id}`),
  tracks: (id: string, cycle: string) => get<Tracks>(`/events/${id}/cycles/${cycle}/tracks`),
  fields: (id: string, cycle: string) => get<Fields>(`/events/${id}/cycles/${cycle}/fields`),
  snapshots: (id: string) => get<{ snapshots: Snapshot[] }>(`/events/${id}/snapshots`),
  isobars: (id: string, cycle: string) => get<{ isobars: Record<string, GeoJSON.FeatureCollection> }>(`/events/${id}/cycles/${cycle}/isobars`),
  districts: (id: string, cycle: string) => get<Districts>(`/events/${id}/cycles/${cycle}/districts`),
  verification: (id: string, cycle: string) => get<Verification>(`/events/${id}/cycles/${cycle}/verification`),
  rainVerification: (id: string, cycle: string) => get<RainVerification>(`/events/${id}/cycles/${cycle}/rain-verification`),
  compare: (id: string, a: string, b: string, hazard = 'very_heavy') => get<Comparison>(`/events/${id}/compare?a=${a}&b=${b}&hazard=${hazard}`),
  sources: () => get<{ sources: Source[] }>('/sources'),
  searchDistricts: (q: string) => get<{ results: DistrictMeta[] }>(`/districts?q=${encodeURIComponent(q)}&limit=12`),
  districtRisk: (did: string, event: string, cycle: string) => get<{
    district: DistrictMeta; risk: DistrictRow | null; no_signal: boolean; windows: Window[]
    trend_vs_previous_cycle: null | { previous_cycle: string; change: Record<string, number> }
    provenance: Provenance
  }>(`/districts/${did}/risk?event=${event}&cycle=${cycle}`),
  draftAdvisory: async (body: { event_id: string; cycle: string; hazard: Hazard; window: number; district_ids: string[] }) => {
    const res = await fetch(`${BASE}/advisories/draft`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    const json = await res.json()
    if (!res.ok) throw new ApiError(res.status, typeof json.detail === 'object' && !Array.isArray(json.detail) ? json.detail : null, JSON.stringify(json.detail))
    return json as { cap_xml: string; validation: { valid: boolean; errors: string[]; schema: string; identifier: string }; districts: { id: string; name: string; state: string; p: number }[]; window: Window; label: string; provenance: Provenance }
  },
}
