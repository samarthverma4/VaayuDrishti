"""Track verification against the IBTrACS best track (RSMC New Delhi fixes).

All errors are great-circle distances at matched valid times. Every number carries n.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.definitions import haversine_km
from pipeline.track.cyclone import interpolate_track

REPORT_LEADS = [0, 24, 48, 72, 96, 120]


def verify_cycle(tracks: dict, best: pd.DataFrame, init: pd.Timestamp, observed_landfall: dict | None) -> dict:
    mean = tracks["mean"]
    by_lead = []
    if mean:
        times = pd.DatetimeIndex([pd.Timestamp(p["valid_time"]) for p in mean])
        bt = interpolate_track(best, times)
        for p, (_, o) in zip(mean, bt.iterrows()):
            if not np.isfinite(o.lat):
                continue
            L = p["lead_h"]
            members = [q for m in tracks["members"] for q in m["points"] if q["lead_h"] == L]
            merr = haversine_km(np.array([q["lat"] for q in members]), np.array([q["lon"] for q in members]), o.lat, o.lon) if members else np.array([])
            by_lead.append({
                "lead_h": L, "valid_time": p["valid_time"],
                "obs_lat": round(float(o.lat), 3), "obs_lon": round(float(o.lon), 3),
                "obs_wind_kt": None if not np.isfinite(o.wind_kt) else round(float(o.wind_kt), 1),
                "mean_error_km": round(float(haversine_km(p["lat"], p["lon"], o.lat, o.lon)), 1),
                "member_error_km_median": round(float(np.median(merr)), 1) if len(merr) else None,
                "spread_km": p["spread_km"],
                "n_members": p["n_members"],
            })

    landfall = None
    lf = tracks.get("landfall")
    if lf and observed_landfall:
        obs_t = pd.Timestamp(observed_landfall["time"])
        fc_t = pd.Timestamp(lf["median_time"])
        landfall = {
            "observed": observed_landfall,
            "forecast_mean": {"lat": lf["mean_lat"], "lon": lf["mean_lon"], "median_time": lf["median_time"]},
            "position_error_km": round(float(haversine_km(lf["mean_lat"], lf["mean_lon"], observed_landfall["lat"], observed_landfall["lon"])), 1),
            "timing_error_h": round((fc_t - obs_t) / pd.Timedelta(hours=1), 1),
            "n_members_landfalling": lf["n_members"],
            "sign_convention": "positive timing error = forecast landfall later than observed",
        }
    return {
        "init": init.isoformat(),
        "by_lead": by_lead,
        "landfall": landfall,
        "truth": "IBTrACS v04r01, RSMC New Delhi fixes, linearly interpolated to forecast valid times",
    }


def summary_by_lead(cycles: list[dict]) -> list[dict]:
    """Mean-track error averaged over cycles at the standard leads, with n."""
    out = []
    for L in REPORT_LEADS:
        errs = [r["mean_error_km"] for c in cycles for r in c["by_lead"] if r["lead_h"] == L]
        spreads = [r["spread_km"] for c in cycles for r in c["by_lead"] if r["lead_h"] == L]
        out.append({"lead_h": L, "n": len(errs),
                    "mean_error_km": round(float(np.mean(errs)), 1) if errs else None,
                    "mean_spread_km": round(float(np.mean(spreads)), 1) if spreads else None})
    return out
