"""Turn cached forecasts into the artifacts the API serves.

    python -m pipeline.build              # every event plus the latest run
    python -m pipeline.build dana-2024    # one event
    python -m pipeline.build --current    # latest run only
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy import ndimage

from pipeline import districts as dist
from pipeline import events as ev_mod
from pipeline import fields, geo, snapshots, verify
from pipeline.config import ARTIFACTS, DATA, DOMAIN
from pipeline.definitions import haversine_km, imd_category, utc_to_ist_iso
from pipeline.ensemble import strike_probability, summarize, trim_over_land
from pipeline.ingest import ecmwf_ens, tigge
from pipeline.track.cyclone import Tracker, TrackPoint, seed_from_best_track

log = logging.getLogger("build")
EVENTS_OUT = ARTIFACTS / "events"
ISOBAR_EVERY_H = 6


def _write(obj, path: Path) -> None:
    fields.write_json(obj, path)


def _provenance(ds: xr.Dataset, init: pd.Timestamp, source_id: str, mode: str) -> dict:
    return {
        "source_id": source_id,
        "source": ds.attrs.get("source", source_id),
        "licence": ds.attrs.get("licence"),
        "model": "ECMWF IFS ENS" if source_id == "ecmwf-ifs-ens" else ds.attrs.get("model", source_id),
        "init_time": init.isoformat(),
        "init_time_ist": utc_to_ist_iso(init),
        "members": int(ds.sizes["member"]),
        "grid_deg": round(float(abs(ds.lat.values[1] - ds.lat.values[0])), 4),
        "leads_h": [int(ds.lead_h.values.min()), int(ds.lead_h.values.max())],
        "lead_steps_h": [int(x) for x in ds.lead_h.values],
        "retrieved_at": ds.attrs.get("retrieved_at"),
        "mode": mode,
        "generated_at": pd.Timestamp.utcnow().isoformat(),
    }


def _best_track_json(track: pd.DataFrame) -> list[dict]:
    out = []
    for r in track.itertuples():
        w = None if not np.isfinite(r.wind_kt) else float(r.wind_kt)
        out.append({"time": r.time.isoformat(), "time_ist": utc_to_ist_iso(r.time), "lat": float(r.lat), "lon": float(r.lon),
                    "wind_kt": w, "pres_hpa": None if not np.isfinite(r.pres_hpa) else float(r.pres_hpa),
                    "category": imd_category(w)})
    return out


def process_cycle(ds: xr.Dataset, init: pd.Timestamp, out: Path, bbox: dict, member_tracks: dict[int, list[TrackPoint]] | None,
                  best: pd.DataFrame | None, landfall: dict | None, source_id: str, mode: str, event: dict) -> dict:
    """Write tracks, fields, isobars, districts and verification for one forecast cycle."""
    lats, lons, leads = ds.lat.values, ds.lon.values, ds.lead_h.values.astype(int)
    prov = _provenance(ds, init, source_id, mode)
    rain, windows = fields.rain_24h(ds)
    win_meta = [{"index": i, "start_h": a, "end_h": b,
                 "valid_start": (init + pd.Timedelta(hours=a)).isoformat(),
                 "valid_end": (init + pd.Timedelta(hours=b)).isoformat()} for i, (a, b) in enumerate(windows)]

    tracks = None
    if member_tracks is not None:
        member_tracks = {m: trim_over_land(p) for m, p in member_tracks.items()}
        tracks = summarize(member_tracks, leads, init)
        tracks.update({"init": init.isoformat(), "provenance": prov,
                       "method": "Per-member MSLP-minimum tracker with closed-low check (≥1 hPa below the 400-600 km annulus mean), seeded at the observed position. Model-derived winds from 0.25° fields underestimate peak intensity."})
        _write(tracks, out / "tracks.json")

    # gridded overlays
    layers = {}
    prob = fields.exceedance(rain)
    for key, arr in prob.items():
        layers[f"p_{key}"] = []
        for w in range(len(windows)):
            p = out / "png" / f"p_{key}_w{w}.png"
            fields.write_png(arr[w], lats, p, "prob")
            layers[f"p_{key}"].append(p.relative_to(out).as_posix())
    layers["rain_mean"] = []
    rmean = rain.mean(axis=1)
    for w in range(len(windows)):
        p = out / "png" / f"rain_mean_w{w}.png"
        fields.write_png(rmean[w], lats, p, "rain")
        layers["rain_mean"].append(p.relative_to(out).as_posix())
    if tracks is not None:
        sp = strike_probability(tracks["members"], lats, lons, windows + [(0, int(leads.max()) + 1)])
        layers["strike"] = []
        for w in range(len(windows) + 1):
            p = out / "png" / f"strike_w{w}.png"
            fields.write_png(sp[w], lats, p, "prob")
            layers["strike"].append(p.relative_to(out).as_posix())
    _write({
        "bounds": fields.image_bounds(lats, lons),
        "windows": win_meta,
        "layers": layers,
        "legends": {"prob": fields.legend("prob"), "rain": fields.legend("rain")},
        "definitions": {
            "p_heavy": "Fraction of members with 24 h rain ≥ 64.5 mm in the cell",
            "p_very_heavy": "Fraction of members with 24 h rain ≥ 115.6 mm in the cell",
            "p_extremely_heavy": "Fraction of members with 24 h rain ≥ 204.5 mm in the cell",
            "rain_mean": "Ensemble-mean 24 h rainfall (mm)",
            "strike": "Fraction of members whose track passes within 120 km of the cell in the window (last entry: whole forecast)",
        },
    }, out / "fields.json")

    # isobars of the ensemble mean, every 6 h
    msl_mean = ds.msl.mean("member").values / 100.0
    iso = {str(L): fields.isobars(msl_mean[k], lats, lons) for k, L in enumerate(leads) if L % ISOBAR_EVERY_H == 0}
    _write(iso, out / "isobars.json")

    # districts
    cells = dist.cell_index(lats, lons, bbox)
    center = ((bbox["lat_min"] + bbox["lat_max"]) / 2, (bbox["lon_min"] + bbox["lon_max"]) / 2)
    rows = dist.build_table(rain, windows, cells, tracks["members"] if tracks else None, center)
    _write({"windows": win_meta, "rows": rows, "definitions": {
        "p_rain": "Fraction of members in which at least one 0.25° cell in the district reaches the IMD threshold in the 24 h window",
        "rain_mm": "10th/50th/90th percentile across members of the district's wettest cell (mm per 24 h)",
        "p_strike": "Fraction of members whose cyclone track passes within 120 km of the district boundary in the window",
    }}, out / "districts.json")

    ver = None
    if tracks is not None and best is not None:
        ver = verify.verify_cycle(tracks, best, init, landfall)
        _write(ver, out / "verification.json")
    _write(prov, out / "provenance.json")
    return {"init": init.isoformat(), "init_ist": utc_to_ist_iso(init), "status": "ready", "members": prov["members"],
            "leads_h": prov["leads_h"], "has_tracks": tracks is not None,
            "members_tracked": sum(1 for m in (tracks or {}).get("members", []) if m["points"]),
            "verification": ver}


def _load_cycle(e: ev_mod.Event, init: pd.Timestamp) -> tuple[xr.Dataset, str] | None:
    if e.ensemble_source == "ecmwf-ifs-ens":
        if not (ecmwf_ens.cache_path(init, e.bbox) / "zarr.json").exists():
            return None
        return ecmwf_ens.load(init, e.bbox), "ecmwf-ifs-ens"
    ds = tigge.load(e.id, init, e.bbox)
    return (ds, "tigge") if ds is not None else None


def build_event(e: ev_mod.Event) -> dict:
    out = EVENTS_OUT / e.id
    if out.exists():
        shutil.rmtree(out)
    cycles = []
    for init in e.cycles:
        loaded = _load_cycle(e, init)
        if loaded is None:
            cycles.append({"init": init.isoformat(), "init_ist": utc_to_ist_iso(init), "status": "missing",
                           "reason": "TIGGE download not loaded (see README: Loading TIGGE data)" if e.ensemble_source == "tigge"
                           else "forecast run not in local cache; run python -m pipeline.fetch"})
            continue
        ds, source_id = loaded
        seed = seed_from_best_track(init, ds.lead_h.values, e.track)
        member_tracks = None
        if seed is not None:
            member_tracks = Tracker(ds).track_all(*seed)
        log.info("%s %s: %s", e.id, init, "tracked" if member_tracks else "no seed")
        cycles.append(process_cycle(ds, init, out / f"{init:%Y%m%d%H}", e.bbox, member_tracks, e.track, e.landfall,
                                    source_id, "historical-replay", {"id": e.id, "name": e.name}))
    vers = [c["verification"] for c in cycles if c.get("verification")]
    for c in cycles:
        c.pop("verification", None)
    peak = e.track.loc[e.track.wind_kt.idxmax()] if e.track.wind_kt.notna().any() else None
    summary = {
        "id": e.id, "sid": e.sid, "name": e.name, "basin": e.basin, "hazard": "cyclone",
        "mode": "historical-replay", "ensemble_source": e.ensemble_source,
        "start": e.start.isoformat(), "end": e.end.isoformat(),
        "landfall": e.landfall, "bbox": e.bbox,
        "peak": None if peak is None else {"wind_kt": float(peak.wind_kt), "time": peak.time.isoformat(), "category": imd_category(float(peak.wind_kt))},
        "cycles": cycles,
        "cycles_ready": sum(c["status"] == "ready" for c in cycles),
        "best_track_source": "IBTrACS v04r01 (RSMC New Delhi)",
        "thumbnail": [[round(float(r.lon), 2), round(float(r.lat), 2)] for r in e.track.iloc[::2].itertuples()],
    }
    snaps = snapshots.build_for_event(e)
    if snaps:
        _write({"snapshots": snaps}, out / "snapshots.json")
    summary["snapshots"] = [{k: s[k] for k in ("id", "valid_time", "kind", "model_min", "distance_km")} for s in snaps]
    detail = {**summary, "best_track": _best_track_json(e.track),
              "verification_summary": verify.summary_by_lead(vers) if vers else None,
              "verification_n_cycles": len(vers)}
    _write(detail, out / "event.json")
    return summary


# ---- current forecast ---------------------------------------------------------------------

def detect_systems(ds: xr.Dataset) -> list[list[tuple[int, float, float]]]:
    """Closed lows over tropical sea in the ensemble-mean MSLP, linked across leads.
    Returns chains of (lead index, lat, lon) lasting at least 24 h."""
    msl = ds.msl.mean("member").values / 100.0
    lats, lons = ds.lat.values, ds.lon.values
    glat, glon = np.meshgrid(lats, lons, indexing="ij")
    leads = ds.lead_h.values
    cands = []
    for k in range(len(leads)):
        f = msl[k]
        mins = (f == ndimage.minimum_filter(f, size=9, mode="nearest"))
        found = []
        for i, j in zip(*np.where(mins)):
            if not (5 <= lats[i] <= 25) or i < 4 or j < 4 or i > len(lats) - 5 or j > len(lons) - 5:
                continue
            d = haversine_km(lats[i], lons[j], glat, glon)
            ring = (d >= 400) & (d <= 600)
            if np.nanmean(f[ring]) - f[i, j] >= 2.0 and not geo.is_land([lats[i]], [lons[j]])[0]:
                found.append((k, float(lats[i]), float(lons[j])))
        cands.append(found)
    chains: list[list[tuple[int, float, float]]] = []
    for k, found in enumerate(cands):
        for c in found:
            for ch in chains:
                last = ch[-1]
                if last[0] == k - 1 and haversine_km(last[1], last[2], c[1], c[2]) < 300:
                    ch.append(c)
                    break
            else:
                chains.append([c])
    return [ch for ch in chains if leads[ch[-1][0]] - leads[ch[0][0]] >= 24]


def build_current() -> dict | None:
    caches = sorted((DATA / "cache" / "ecmwf-ifs-ens").glob("*_0_35_55_100.zarr"))
    if not caches:
        log.warning("no latest run cached; run python -m pipeline.fetch --latest")
        return None
    path = caches[-1]
    init = pd.Timestamp(path.name.split("_")[0])
    ds = xr.open_zarr(path, consolidated=False).load()
    out = ARTIFACTS / "current" / f"{init:%Y%m%d%H}"
    if out.parent.exists():
        shutil.rmtree(out.parent)
    chains = detect_systems(ds)
    systems = []
    tracker = Tracker(ds)
    for n, ch in enumerate(chains):
        k0, lat0, lon0 = ch[0]
        mt = tracker.track_all(k0, (lat0, lon0))
        sub = out / f"system-{n + 1}"
        info = process_cycle(ds, init, sub, DOMAIN, mt, None, None, "ecmwf-ifs-ens", "current-forecast", {"id": f"system-{n + 1}", "name": f"System {n + 1}"})
        systems.append({"id": f"system-{n + 1}", "first_lead_h": int(ds.lead_h.values[k0]), "first_lat": lat0, "first_lon": lon0, **info})
    base = process_cycle(ds, init, out / "domain", DOMAIN, None, None, None, "ecmwf-ifs-ens", "current-forecast", {"id": "domain", "name": "India"})
    summary = {"init": init.isoformat(), "init_ist": utc_to_ist_iso(init), "retrieved_at": ds.attrs.get("retrieved_at"),
               "domain": DOMAIN, "systems": systems, "domain_status": base["status"], "members": base["members"],
               "detection": "Closed lows (≥2 hPa below the 400-600 km annulus) over sea between 5° and 25° N in the ensemble-mean MSLP, persisting ≥24 h"}
    _write(summary, ARTIFACTS / "current" / "current.json")
    return summary


def write_index(summaries: list[dict], current: dict | None) -> None:
    import yaml

    sources = yaml.safe_load((DATA / "sources.yaml").read_text())
    _write({"generated_at": pd.Timestamp.utcnow().isoformat(), "events": summaries, "current": current,
            "sources": sources["sources"]}, ARTIFACTS / "index.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("event_ids", nargs="*")
    ap.add_argument("--current", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not (ARTIFACTS / "geo" / "districts.geojson").exists():
        geo.build()
    existing = {}
    idx = ARTIFACTS / "index.json"
    if idx.exists():
        prev = json.loads(idx.read_text())
        existing = {e["id"]: e for e in prev.get("events", [])}
        current = prev.get("current")
    else:
        current = None
    summaries = []
    for e in ev_mod.load_events():
        if args.current or (args.event_ids and e.id not in args.event_ids):
            if e.id in existing:
                summaries.append(existing[e.id])
            continue
        summaries.append(build_event(e))
    if args.current or not args.event_ids:
        current = build_current() or current
    write_index(summaries, current)


if __name__ == "__main__":
    main()
