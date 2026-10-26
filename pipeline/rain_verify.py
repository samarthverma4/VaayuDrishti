"""Rainfall verification of ensemble forecasts against IMD gridded daily rainfall.

Only IMD days whose 24 h window (03 UTC to 03 UTC) coincides exactly with forecast output steps are
scored; nothing is interpolated in time. Each day is scored on the IMD land cells within 300 km of
the observed (best-track) storm positions during that window, so the storm's rain dominates the
scores; days when the storm is not in the best track are skipped. IMD is a gauge analysis and the forecast a 0.25 degree grid-box mean, so point extremes are
smoothed in both; scores describe this case study, not general skill.

Per day:
  - ensemble-mean rainfall: mean error (bias) and mean absolute error, in mm
  - for each IMD threshold, "forecast yes" = at least half of members reach it in the cell:
    hits, misses, false alarms, POD, FAR, CSI; Brier score of the member fraction;
    Fractions Skill Score of the yes/no fields at 1, 3, 5 and 9 cell neighbourhoods
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr
from scipy.ndimage import uniform_filter

from pipeline.definitions import RAIN_THRESHOLDS_MM, haversine_km
from pipeline.ingest import imd_rain
from pipeline.track.cyclone import interpolate_track

YES_FRACTION = 0.5
FSS_SCALES = (1, 3, 5, 9)
MIN_CELLS = 20
STORM_RADIUS_KM = 300.0


def _ratio(a: float, b: float) -> float | None:
    return None if b == 0 else round(a / b, 3)


def fss(fc: np.ndarray, ob: np.ndarray, valid: np.ndarray, n: int) -> float | None:
    """Fractions Skill Score (Roberts and Lean 2008) of binary fields on the valid cells, n x n neighbourhood."""
    v = valid.astype(float)
    den = uniform_filter(v, n, mode="constant")
    with np.errstate(invalid="ignore", divide="ignore"):
        pf = uniform_filter(fc * v, n, mode="constant") / den
        po = uniform_filter(ob * v, n, mode="constant") / den
    pf, po = pf[valid], po[valid]
    ref = np.mean(pf ** 2) + np.mean(po ** 2)
    return None if ref == 0 else round(float(1 - np.mean((pf - po) ** 2) / ref), 3)


def _member_accum(ds: xr.Dataset, a: int, b: int) -> np.ndarray:
    """Per-member accumulation (mm) over forecast hours (a, b]: (member, lat, lon)."""
    leads = ds.lead_h.values.astype(int)
    steps = np.diff(leads, prepend=leads[0]) * 3600.0
    sel = (leads > a) & (leads <= b)
    return np.nansum(ds.prate.values[sel] * steps[sel, None, None, None], axis=0)


def _aligned(leads: np.ndarray, a: int, b: int) -> bool:
    """True when (a, b] is covered exactly by output steps (a is 0 or an output step, b is an output step)."""
    s = set(int(x) for x in leads)
    return a >= 0 and (a == 0 or a in s) and b in s


def _observed_on(lats: np.ndarray, lons: np.ndarray, obs: np.ndarray) -> np.ndarray:
    """IMD field on the forecast grid (both 0.25 degree, same lattice); NaN where IMD has no cell."""
    out = np.full((lats.size, lons.size), np.nan, np.float32)
    iy = np.round((lats - imd_rain.LATS[0]) / 0.25).astype(int)
    ix = np.round((lons - imd_rain.LONS[0]) / 0.25).astype(int)
    oky = (iy >= 0) & (iy < imd_rain.LATS.size) & np.isclose(imd_rain.LATS[np.clip(iy, 0, imd_rain.LATS.size - 1)], lats)
    okx = (ix >= 0) & (ix < imd_rain.LONS.size) & np.isclose(imd_rain.LONS[np.clip(ix, 0, imd_rain.LONS.size - 1)], lons)
    out[np.ix_(oky, okx)] = obs[np.ix_(iy[oky], ix[okx])]
    return out


def storm_region(track: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, lats, lons) -> np.ndarray | None:
    """Cells within STORM_RADIUS_KM of the best track (hourly) between start and end; None if no track then."""
    pts = interpolate_track(track, pd.date_range(start, end, freq="1h")).dropna(subset=["lat", "lon"])
    if pts.empty:
        return None
    glat, glon = np.meshgrid(lats, lons, indexing="ij")
    d = np.min([haversine_km(glat, glon, la, lo) for la, lo in zip(pts.lat.values, pts.lon.values)], axis=0)
    return d <= STORM_RADIUS_KM


def score_day(members: np.ndarray, obs: np.ndarray) -> dict:
    """members: (member, lat, lon) mm; obs: (lat, lon) mm with NaN outside the scored area."""
    valid = np.isfinite(obs)
    mean = members.mean(axis=0)
    err = mean[valid] - obs[valid]
    out = {"n_cells": int(valid.sum()),
           "obs_mean_mm": round(float(obs[valid].mean()), 1), "fc_mean_mm": round(float(mean[valid].mean()), 1),
           "obs_max_mm": round(float(obs[valid].max()), 1), "fc_mean_max_mm": round(float(mean[valid].max()), 1),
           "bias_mm": round(float(err.mean()), 1), "mae_mm": round(float(np.abs(err).mean()), 1), "thresholds": {}}
    for key, thr in RAIN_THRESHOLDS_MM.items():
        frac = (members >= thr).mean(axis=0)
        fy = frac >= YES_FRACTION
        oy = np.where(valid, obs >= thr, False)
        h = int((fy & oy & valid).sum()); m = int((~fy & oy & valid).sum()); f = int((fy & ~oy & valid).sum())
        out["thresholds"][key] = {
            "threshold_mm": thr, "observed_cells": int(oy.sum()), "forecast_cells": int((fy & valid).sum()),
            "hits": h, "misses": m, "false_alarms": f,
            "pod": _ratio(h, h + m), "far": _ratio(f, h + f), "csi": _ratio(h, h + m + f),
            "brier": round(float(np.mean((frac[valid] - oy[valid]) ** 2)), 4),
            "fss": {str(n): fss(fy.astype(float), oy.astype(float), valid, n) for n in FSS_SCALES},
        }
    return out


def verify_cycle(ds: xr.Dataset, init: pd.Timestamp, track: pd.DataFrame) -> dict:
    """Score every IMD day inside the forecast range near the observed storm."""
    lats, lons, leads = ds.lat.values, ds.lon.values, ds.lead_h.values.astype(int)
    days, skipped, years = [], [], set()
    first = (init + pd.Timedelta(hours=1)).normalize() + pd.Timedelta(days=1)
    while True:
        end = imd_rain.window_end(first)
        b = int((end - init) / pd.Timedelta(hours=1))
        a = b - 24
        if b > leads.max():
            break
        obs_day = imd_rain.day(first)
        if obs_day is None:
            skipped.append({"date": first.date().isoformat(), "reason": f"IMD {first.year} file not downloaded"})
        elif not _aligned(leads, a, b):
            skipped.append({"date": first.date().isoformat(), "reason": f"forecast output at T+{a}/T+{b} h not available "
                            "(6-hourly steps); the 03 UTC window cannot be formed without time interpolation"})
        else:
            region = storm_region(track, end - pd.Timedelta(hours=24), end, lats, lons)
            obs = np.where(region, _observed_on(lats, lons, obs_day), np.nan) if region is not None else None
            if obs is None:
                skipped.append({"date": first.date().isoformat(), "reason": "storm not in the best track during this day"})
            elif np.isfinite(obs).sum() < MIN_CELLS:
                skipped.append({"date": first.date().isoformat(), "reason": f"fewer than {MIN_CELLS} IMD land cells within {STORM_RADIUS_KM:.0f} km of the storm (at sea)"})
            else:
                years.add(first.year)
                days.append({"date": first.date().isoformat(), "start_h": a, "end_h": b, "lead_day": a // 24 + 1,
                             "valid_start": (end - pd.Timedelta(hours=24)).isoformat(), "valid_end": end.isoformat(),
                             **score_day(_member_accum(ds, a, b), obs)})
        first += pd.Timedelta(days=1)
    return {"init": init.isoformat(), "days": days, "skipped": skipped,
            "truth": imd_rain.SOURCE + "; day D = 24 h ending 03 UTC (08:30 IST) on D",
            "area": f"IMD land cells within {STORM_RADIUS_KM:.0f} km of the observed storm positions during each day",
            "yes_rule": f"forecast yes when at least {int(YES_FRACTION * 100)}% of members reach the threshold in the cell",
            "fss_scales_cells": list(FSS_SCALES), "cell_deg": 0.25,
            "observations": [imd_rain.provenance(y) for y in sorted(years)]}


def summary_by_lead_day(cycles: list[dict]) -> list[dict]:
    """Pool days from all cycles by lead day: mean MAE and bias, and summed contingency counts, with n."""
    out = []
    for d in sorted({x["lead_day"] for c in cycles for x in c["days"]}):
        rows = [x for c in cycles for x in c["days"] if x["lead_day"] == d]
        row = {"lead_day": d, "n_days": len(rows),
               "mae_mm": round(float(np.mean([r["mae_mm"] for r in rows])), 1),
               "bias_mm": round(float(np.mean([r["bias_mm"] for r in rows])), 1), "thresholds": {}}
        for key in RAIN_THRESHOLDS_MM:
            h = sum(r["thresholds"][key]["hits"] for r in rows)
            m = sum(r["thresholds"][key]["misses"] for r in rows)
            f = sum(r["thresholds"][key]["false_alarms"] for r in rows)
            row["thresholds"][key] = {"hits": h, "misses": m, "false_alarms": f,
                                      "pod": _ratio(h, h + m), "far": _ratio(f, h + f), "csi": _ratio(h, h + m + f)}
        out.append(row)
    return out
