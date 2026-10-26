"""Single-field model snapshots from TIGGE GRIB files (for example the access-probe download).

A snapshot is one control-forecast mean-sea-level-pressure field at T+0 (the model analysis state).
It supports a map of isobars and a check of the model's low against the observed best track. It is
not a forecast: no tracks, spread or probabilities are derived from it.

Source files are opened read-only and never modified; provenance (path, SHA-256, size, GRIB keys)
is carried into the artifact.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import fields
from pipeline.definitions import haversine_km, utc_to_ist_iso
from pipeline.ingest.tigge import TIGGE_DIR, _Regridder, _target_grid
from pipeline.track.cyclone import interpolate_track

log = logging.getLogger(__name__)
KEYS = ["centre", "marsClass", "marsStream", "marsType", "shortName", "name", "units", "paramId", "typeOfLevel",
        "dataDate", "dataTime", "stepRange", "number", "gridType", "N", "numberOfDataPoints", "bitsPerValue",
        "packingType", "productionStatusOfProcessedData"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _messages(path: Path):
    """Yield (keys, lats, lons, values) for each control-forecast MSLP message at step 0."""
    import eccodes

    with open(path, "rb") as fh:
        while (h := eccodes.codes_grib_new_from_file(fh)) is not None:
            try:
                meta = {}
                for k in KEYS:
                    try:
                        meta[k] = eccodes.codes_get(h, k)
                    except Exception:  # noqa: BLE001 - key absent in this message
                        meta[k] = None
                if meta["shortName"] == "msl" and str(meta["stepRange"]) == "0" and meta["marsType"] == "cf":
                    lats = eccodes.codes_get_array(h, "latitudes")
                    lons = eccodes.codes_get_array(h, "longitudes")
                    vals = eccodes.codes_get_values(h)
                    yield meta, lats, ((lons + 180) % 360) - 180, vals
            finally:
                eccodes.codes_release(h)


def build_for_event(ev) -> list[dict]:
    """Snapshots whose valid time falls within the event's best-track period, from any TIGGE file."""
    out = []
    try:
        import eccodes  # noqa: F401
    except ImportError:
        return out
    for path in sorted(TIGGE_DIR.rglob("*.grib")):
        for meta, lats, lons, vals in _messages(path):
            t = pd.Timestamp(f"{meta['dataDate']}") + pd.Timedelta(hours=int(meta["dataTime"]) // 100)
            if not (ev.start <= t <= ev.end):
                continue
            k = int(np.argmin(vals))
            bt = interpolate_track(ev.track, pd.DatetimeIndex([t])).iloc[0]
            obs = ev.track[ev.track.time == t]
            # isobars on the common 0.25 degree grid (linear interpolation from the native points)
            bbox = {"lat_min": float(np.ceil(lats.min() * 4) / 4), "lat_max": float(np.floor(lats.max() * 4) / 4),
                    "lon_min": float(np.ceil(lons.min() * 4) / 4), "lon_max": float(np.floor(lons.max() * 4) / 4)}
            glat, glon = _target_grid(bbox)
            grid = _Regridder(lats, lons, glat, glon)(vals[None, :].astype(np.float32))[0] / 100.0
            out.append({
                "id": f"{t:%Y%m%d%H}-{meta['marsType']}-msl",
                "valid_time": t.isoformat(), "valid_time_ist": utc_to_ist_iso(t),
                "kind": "model analysis (control forecast, T+0)",
                "variable": "mean sea-level pressure",
                "model_min": {"lat": round(float(lats[k]), 3), "lon": round(float(lons[k]), 3), "msl_hpa": round(float(vals[k]) / 100, 1)},
                "field_range_hpa": [round(float(vals.min()) / 100, 1), round(float(vals.max()) / 100, 1)],
                "coverage": {"lat": [round(float(lats.min()), 3), round(float(lats.max()), 3)], "lon": [round(float(lons.min()), 3), round(float(lons.max()), 3)]},
                "observed": None if not np.isfinite(bt.lat) else {
                    "lat": round(float(bt.lat), 3), "lon": round(float(bt.lon), 3),
                    "wind_kt": None if obs.empty or not np.isfinite(obs.wind_kt.iloc[0]) else float(obs.wind_kt.iloc[0]),
                    "pres_hpa": None if obs.empty or not np.isfinite(obs.pres_hpa.iloc[0]) else float(obs.pres_hpa.iloc[0]),
                    "exact_fix": not obs.empty,
                },
                "distance_km": None if not np.isfinite(bt.lat) else round(float(haversine_km(lats[k], lons[k], bt.lat, bt.lon)), 1),
                "isobars": fields.isobars(grid, glat, glon),
                "isobar_note": "2 hPa isobars after linear interpolation from the native grid to 0.25°",
                "provenance": {
                    "file": str(path.relative_to(TIGGE_DIR.parent.parent.parent)),
                    "sha256": _sha256(path), "bytes": path.stat().st_size,
                    "downloaded_at": pd.Timestamp(path.stat().st_mtime, unit="s").isoformat(),
                    "source": "TIGGE via ECMWF Data Store", "licence": "CC BY 4.0 (ECMWF)" if meta["centre"] == "ecmf" else "CC BY-NC 4.0",
                    "grib": meta,
                },
                "not_available": "No forecast lead times, no ensemble members, no wind or rainfall: tracking, spread, probabilities and verification need the full TIGGE download.",
            })
            log.info("%s: snapshot %s from %s", ev.id, t, path.name)
    return out
