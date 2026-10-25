"""Ensemble track products: mean track, spread, envelope, strike probability, landfall."""
from __future__ import annotations

import numpy as np
import pandas as pd
import shapely
from scipy.spatial import cKDTree
from shapely.geometry import Polygon, mapping

from pipeline import geo
from pipeline.definitions import (
    EARTH_RADIUS_KM, SPREAD_QUANTILE, STRIKE_RADIUS_KM, destination, haversine_km,
    imd_category, spherical_mean,
)
from pipeline.track.cyclone import TrackPoint

MIN_ALIVE_FRACTION = 0.3
OVERLAND_STOP_DEPTH_HPA = 2.0


def trim_over_land(points: list[TrackPoint]) -> list[TrackPoint]:
    """Stop a member track once it is over land and its low has filled below 2 hPa depth."""
    if not points:
        return points
    land = geo.is_land([p.lat for p in points], [p.lon for p in points])
    for i, (p, on_land) in enumerate(zip(points, land)):
        if on_land and p.depth_hpa < OVERLAND_STOP_DEPTH_HPA:
            return points[:i]
    return points


def member_landfall(points: list[TrackPoint], init: pd.Timestamp) -> dict | None:
    """First sea-to-land crossing, located by sampling each segment at 2 km resolution."""
    if len(points) < 2:
        return None
    lats = np.array([p.lat for p in points])
    lons = np.array([p.lon for p in points])
    land = geo.is_land(lats, lons)
    if land[0]:
        return None
    idx = np.where(land)[0]
    if len(idx) == 0:
        return None
    i = int(idx[0])
    a, b = points[i - 1], points[i]
    n = max(2, int(haversine_km(a.lat, a.lon, b.lat, b.lon) / 2))
    f = np.linspace(0, 1, n)
    sl, so = a.lat + (b.lat - a.lat) * f, a.lon + (b.lon - a.lon) * f
    j = int(np.argmax(geo.is_land(sl, so)))
    lead = a.lead_h + (b.lead_h - a.lead_h) * f[j]
    return {
        "lat": round(float(sl[j]), 3), "lon": round(float(so[j]), 3),
        "lead_h": round(float(lead), 1),
        "time": (init + pd.Timedelta(hours=float(lead))).isoformat(),
        "vmax_kt": round(max(a.vmax_kt, b.vmax_kt), 1),
    }


def _circle(lat: float, lon: float, r_km: float, n: int = 48) -> Polygon:
    b = np.linspace(0, 360, n, endpoint=False)
    la, lo = destination(lat, lon, b, r_km)
    return Polygon(np.column_stack([lo, la]))


def summarize(member_tracks: dict[int, list[TrackPoint]], leads: np.ndarray, init: pd.Timestamp) -> dict:
    n_members = len(member_tracks)
    by_lead: dict[int, list[tuple[int, TrackPoint]]] = {int(L): [] for L in leads}
    for m, pts in member_tracks.items():
        for p in pts:
            by_lead[p.lead_h].append((m, p))

    mean = []
    for L in leads:
        items = by_lead[int(L)]
        if len(items) < max(5, MIN_ALIVE_FRACTION * n_members):
            continue
        la = [p.lat for _, p in items]
        lo = [p.lon for _, p in items]
        mlat, mlon = spherical_mean(la, lo)
        dist = haversine_km(np.array(la), np.array(lo), mlat, mlon)
        vmax = np.array([p.vmax_kt for _, p in items])
        msl = np.array([p.msl_hpa for _, p in items])
        mean.append({
            "lead_h": int(L),
            "valid_time": (init + pd.Timedelta(hours=int(L))).isoformat(),
            "lat": round(mlat, 3), "lon": round(mlon, 3),
            "n_members": len(items),
            "spread_km": round(float(np.mean(dist)), 1),
            "radius80_km": round(float(np.quantile(dist, SPREAD_QUANTILE)), 1),
            "vmax_kt": {"p10": round(float(np.percentile(vmax, 10)), 1), "median": round(float(np.median(vmax)), 1), "p90": round(float(np.percentile(vmax, 90)), 1)},
            "msl_hpa": {"p10": round(float(np.percentile(msl, 10)), 1), "median": round(float(np.median(msl)), 1), "p90": round(float(np.percentile(msl, 90)), 1)},
            "category_median": imd_category(float(np.median(vmax))),
        })

    # envelope: circles of the 80% radius along the mean track, joined by hulls of consecutive pairs
    circles = [_circle(p["lat"], p["lon"], max(p["radius80_km"], 15.0)) for p in mean]
    parts = [shapely.convex_hull(shapely.union(a, b)) for a, b in zip(circles, circles[1:])] or circles
    envelope = shapely.union_all(parts) if parts else None

    landfalls = {m: member_landfall(pts, init) for m, pts in member_tracks.items()}
    lf = [v for v in landfalls.values() if v]
    landfall_summary = None
    if lf:
        mlat, mlon = spherical_mean([v["lat"] for v in lf], [v["lon"] for v in lf])
        leads_lf = np.array([v["lead_h"] for v in lf])
        landfall_summary = {
            "n_members": len(lf), "fraction": round(len(lf) / n_members, 3),
            "mean_lat": round(mlat, 3), "mean_lon": round(mlon, 3),
            "median_lead_h": round(float(np.median(leads_lf)), 1),
            "lead_h_p10": round(float(np.percentile(leads_lf, 10)), 1),
            "lead_h_p90": round(float(np.percentile(leads_lf, 90)), 1),
            "median_time": (init + pd.Timedelta(hours=float(np.median(leads_lf)))).isoformat(),
        }

    return {
        "n_members": n_members,
        "members": [
            {"member": m, "points": [
                {"lead_h": p.lead_h, "lat": round(p.lat, 3), "lon": round(p.lon, 3),
                 "msl_hpa": round(p.msl_hpa, 1), "depth_hpa": round(p.depth_hpa, 1), "vmax_kt": round(p.vmax_kt, 1)}
                for p in pts], "landfall": landfalls[m]}
            for m, pts in member_tracks.items()
        ],
        "mean": mean,
        "envelope": mapping(envelope) if envelope is not None and not envelope.is_empty else None,
        "envelope_definition": f"Region swept by circles around the ensemble-mean position containing {int(SPREAD_QUANTILE * 100)}% of member positions at each lead. Not a calibrated probability cone.",
        "landfall": landfall_summary,
    }


def _unit(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    return np.column_stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])


def densify(points: list[dict], step_km: float = 20.0) -> np.ndarray:
    """(lead_h, lat, lon) samples every ~step_km along a member track."""
    if len(points) == 1:
        p = points[0]
        return np.array([[p["lead_h"], p["lat"], p["lon"]]])
    out = []
    for a, b in zip(points, points[1:]):
        n = max(1, int(haversine_km(a["lat"], a["lon"], b["lat"], b["lon"]) / step_km))
        f = np.linspace(0, 1, n, endpoint=False)
        out.append(np.column_stack([a["lead_h"] + (b["lead_h"] - a["lead_h"]) * f,
                                    a["lat"] + (b["lat"] - a["lat"]) * f,
                                    a["lon"] + (b["lon"] - a["lon"]) * f]))
    p = points[-1]
    out.append(np.array([[p["lead_h"], p["lat"], p["lon"]]]))
    return np.vstack(out)


def strike_probability(members: list[dict], lats: np.ndarray, lons: np.ndarray, windows: list[tuple[int, int]]) -> np.ndarray:
    """P(member track passes within STRIKE_RADIUS_KM of each grid cell) per lead window.
    Returns (n_windows, ny, nx). Members without a track count as no strike."""
    glat, glon = np.meshgrid(lats, lons, indexing="ij")
    tree = cKDTree(_unit(glat.ravel(), glon.ravel()))
    chord = 2 * np.sin(STRIKE_RADIUS_KM / EARTH_RADIUS_KM / 2)
    out = np.zeros((len(windows), glat.size))
    for mem in members:
        if not mem["points"]:
            continue
        s = densify(mem["points"])
        for w, (a, b) in enumerate(windows):
            sel = s[(s[:, 0] >= a) & (s[:, 0] < b)]
            if len(sel) == 0:
                continue
            hit = np.zeros(glat.size, bool)
            for idx in tree.query_ball_point(_unit(sel[:, 1], sel[:, 2]), chord):
                hit[idx] = True
            out[w] += hit
    return (out / max(1, len(members))).reshape(len(windows), *glat.shape)
