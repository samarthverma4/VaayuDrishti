"""Per-member tropical cyclone tracker.

Reduced input profile (MSLP + 10 m wind), because the open ENS archive has no 850 hPa
winds or vorticity. Method, per member:

1. Seed at the observed best-track position at the first lead it exists (the standard
   practice for verifying forecast tracks of a named storm).
2. At each later step, extrapolate the last motion to get a first guess and search for the
   MSLP minimum within a radius that scales with the step length.
3. Accept the minimum only if it is a closed low: interior (not on the search edge) and at
   least MIN_DEPTH_HPA below the mean pressure in a 400-600 km annulus.
4. Allow one missed step (keep the extrapolated guess), then stop.

The result is model-derived: 0.25 degree winds underestimate peak intensity.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import xarray as xr

from pipeline.definitions import KT_PER_MS, haversine_km

MIN_DEPTH_HPA = 1.0
ANNULUS_KM = (400.0, 600.0)
VMAX_RADIUS_KM = 300.0
MAX_SPEED_KMH = 45.0  # generous cap on storm motion
BASE_SEARCH_KM = 150.0


@dataclass
class TrackPoint:
    lead_h: int
    lat: float
    lon: float
    msl_hpa: float
    depth_hpa: float
    vmax_kt: float


def interpolate_track(track: pd.DataFrame, times: pd.DatetimeIndex) -> pd.DataFrame:
    """Best track linearly interpolated to `times` (NaN outside its time span)."""
    t = track.set_index("time")[["lat", "lon", "wind_kt"]].astype(float)
    t = t[~t.index.duplicated()]
    x = t.index.view("int64").astype(float)
    xi = pd.DatetimeIndex(times).view("int64").astype(float)
    out = pd.DataFrame(index=pd.DatetimeIndex(times))
    for c in t.columns:
        y = t[c].values
        ok = np.isfinite(y)
        out[c] = np.interp(xi, x[ok], y[ok], left=np.nan, right=np.nan) if ok.any() else np.nan
    return out


def _quadratic_refine(field: np.ndarray, i: int, j: int, lats: np.ndarray, lons: np.ndarray) -> tuple[float, float]:
    """Sub-grid minimum from a 1-D parabola through the 3 points in each direction."""
    def offset(fm, f0, fp):
        den = fm - 2 * f0 + fp
        return 0.0 if den <= 0 else float(np.clip(0.5 * (fm - fp) / den, -0.5, 0.5))

    ny, nx = field.shape
    di = offset(field[i - 1, j], field[i, j], field[i + 1, j]) if 0 < i < ny - 1 else 0.0
    dj = offset(field[i, j - 1], field[i, j], field[i, j + 1]) if 0 < j < nx - 1 else 0.0
    dlat = lats[1] - lats[0]
    dlon = lons[1] - lons[0]
    return float(lats[i] + di * dlat), float(lons[j] + dj * dlon)


class Tracker:
    def __init__(self, ds: xr.Dataset):
        self.lats = ds.lat.values
        self.lons = ds.lon.values
        self.leads = ds.lead_h.values.astype(int)
        self.msl = ds.msl.values / 100.0  # hPa, (lead, member, lat, lon)
        self.wspd = np.hypot(ds.u10.values, ds.v10.values)
        self.glat, self.glon = np.meshgrid(self.lats, self.lons, indexing="ij")

    def _find(self, k: int, m: int, guess: tuple[float, float], radius: float) -> TrackPoint | None:
        d = haversine_km(guess[0], guess[1], self.glat, self.glon)
        inside = d <= radius
        if not inside.any():
            return None
        f = self.msl[k, m]
        masked = np.where(inside, f, np.inf)
        i, j = np.unravel_index(np.argmin(masked), masked.shape)
        if d[i, j] > 0.9 * radius:  # minimum sits on the search edge: no closed low
            return None
        lat, lon = _quadratic_refine(f, i, j, self.lats, self.lons)
        dc = haversine_km(lat, lon, self.glat, self.glon)
        ring = (dc >= ANNULUS_KM[0]) & (dc <= ANNULUS_KM[1])
        if ring.sum() < 8:
            return None
        depth = float(np.nanmean(f[ring]) - f[i, j])
        if depth < MIN_DEPTH_HPA:
            return None
        near = dc <= VMAX_RADIUS_KM
        vmax = float(np.nanmax(self.wspd[k, m][near])) * KT_PER_MS
        return TrackPoint(int(self.leads[k]), lat, lon, float(f[i, j]), depth, vmax)

    def track_member(self, m: int, k0: int, seed: tuple[float, float]) -> list[TrackPoint]:
        pts: list[TrackPoint] = []
        guess = seed
        misses = 0
        for k in range(k0, len(self.leads)):
            dt = self.leads[k] - self.leads[k - 1] if k > 0 else 3
            if pts:
                last = pts[-1]
                if len(pts) >= 2:
                    prev = pts[-2]
                    span = last.lead_h - prev.lead_h
                    f = (self.leads[k] - last.lead_h) / span
                    guess = (last.lat + (last.lat - prev.lat) * f, last.lon + (last.lon - prev.lon) * f)
                else:
                    guess = (last.lat, last.lon)
            radius = BASE_SEARCH_KM + MAX_SPEED_KMH * dt * 0.5 if pts else 300.0
            p = self._find(k, m, guess, radius)
            if p is None:
                misses += 1
                if misses > 1 or not pts:
                    break
                continue
            misses = 0
            pts.append(p)
        return pts

    def track_all(self, seed_lead_index: int, seed: tuple[float, float]) -> dict[int, list[TrackPoint]]:
        return {m: self.track_member(m, seed_lead_index, seed) for m in range(self.msl.shape[1])}


def seed_from_best_track(init: pd.Timestamp, leads: np.ndarray, best: pd.DataFrame) -> tuple[int, tuple[float, float]] | None:
    """First lead at which the observed storm exists, and its observed position then."""
    times = init + pd.to_timedelta(leads, unit="h")
    bt = interpolate_track(best, times)
    ok = np.where(bt.lat.notna().values)[0]
    if len(ok) == 0:
        return None
    k = int(ok[0])
    return k, (float(bt.lat.iloc[k]), float(bt.lon.iloc[k]))
