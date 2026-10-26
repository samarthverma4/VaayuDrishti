"""Gridded products: 24 h rainfall per member, exceedance probabilities, mean isobars,
and georeferenced PNG overlays (resampled to Web Mercator rows so MapLibre places them exactly)."""
from __future__ import annotations

import json
from pathlib import Path

import contourpy
import numpy as np
import xarray as xr
from PIL import Image

from pipeline.definitions import RAIN_THRESHOLDS_MM

WINDOW_H = 24


def rain_windows(leads: np.ndarray) -> list[tuple[int, int]]:
    last = int(leads.max())
    return [(a, a + WINDOW_H) for a in range(0, last - WINDOW_H + 1, WINDOW_H)]


def rain_24h(ds: xr.Dataset) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """24 h accumulations (mm) per member: (n_windows, member, lat, lon).

    prate at lead L is the mean rate over the step ending at L, so the accumulation over
    (a, b] is the sum of prate * step_seconds for steps ending in (a, b].
    """
    leads = ds.lead_h.values.astype(int)
    pr = ds.prate.values  # kg m-2 s-1 == mm/s
    steps = np.diff(leads, prepend=leads[0]) * 3600.0
    windows = rain_windows(leads)
    out = np.zeros((len(windows), pr.shape[1], pr.shape[2], pr.shape[3]), np.float32)
    for w, (a, b) in enumerate(windows):
        sel = (leads > a) & (leads <= b)
        out[w] = np.nansum(pr[sel] * steps[sel, None, None, None], axis=0)
    return out, windows


def exceedance(rain: np.ndarray) -> dict[str, np.ndarray]:
    """Fraction of members at or above each IMD threshold: {key: (n_windows, lat, lon)}."""
    return {k: (rain >= thr).mean(axis=1) for k, thr in RAIN_THRESHOLDS_MM.items()}


# ---- rendering -------------------------------------------------------------------------

# Sequential ramps (perceptually ordered). Probability: pale teal to deep magenta;
# rain amount: viridis-like.
PROB_STOPS = [(0.0, (57, 188, 167, 0)), (0.1, (57, 188, 167, 120)), (0.3, (102, 220, 231, 170)),
              (0.5, (243, 184, 92, 200)), (0.7, (239, 107, 97, 220)), (1.0, (216, 87, 151, 235))]
RAIN_STOPS = [(0.0, (68, 1, 84, 0)), (10, (59, 82, 139, 110)), (35, (33, 145, 140, 160)),
              (64.5, (94, 201, 98, 190)), (115.6, (253, 231, 37, 215)), (204.5, (255, 255, 255, 235))]

# EFI: transparent below 0.3, ECMWF's usual "unusual" (0.5) and "very unusual" (0.8) marks highlighted.
EFI_STOPS = [(0.3, (102, 220, 231, 0)), (0.5, (243, 184, 92, 170)), (0.8, (239, 107, 97, 215)), (1.0, (216, 87, 151, 240))]
# SOT: transparent below 0 (ensemble 90th percentile under the climate 99th).
SOT_STOPS = [(0.0, (243, 184, 92, 0)), (0.5, (243, 184, 92, 160)), (1.5, (239, 107, 97, 210)), (3.0, (216, 87, 151, 240))]
STOPS = {"prob": PROB_STOPS, "rain": RAIN_STOPS, "efi": EFI_STOPS, "sot": SOT_STOPS}
UNITS = {"prob": "fraction of members", "rain": "mm per 24 h", "efi": "Extreme Forecast Index (-1 to 1)",
         "sot": "Shift of Tails (> 0: ensemble 90th percentile beyond the climate 99th)"}


def _ramp(values: np.ndarray, stops) -> np.ndarray:
    xs = np.array([s[0] for s in stops], float)
    cs = np.array([s[1] for s in stops], float)
    v = np.nan_to_num(values, nan=xs[0])
    rgba = np.stack([np.interp(v, xs, cs[:, c]) for c in range(4)], axis=-1)
    rgba[np.isnan(values) | (v < xs[0])] = 0
    return rgba.astype(np.uint8)


def _merc_y(lat):
    return np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


def to_mercator_rows(field: np.ndarray, lats: np.ndarray, upsample: int = 4) -> np.ndarray:
    """Resample a lat-descending regular grid onto rows equally spaced in Mercator y."""
    ny = field.shape[0] * upsample
    y = np.linspace(_merc_y(lats[0]), _merc_y(lats[-1]), ny)
    lat_rows = np.degrees(2 * np.arctan(np.exp(y)) - np.pi / 2)
    asc = lats[::-1]
    fidx = np.interp(lat_rows, asc, np.arange(len(asc)))
    i0 = np.clip(np.floor(fidx).astype(int), 0, len(asc) - 1)
    i1 = np.clip(i0 + 1, 0, len(asc) - 1)
    w = (fidx - i0)[:, None]
    f = field[::-1]
    rows = f[i0] * (1 - w) + f[i1] * w
    # upsample columns linearly too, for smooth display
    nx = field.shape[1]
    xi = np.linspace(0, nx - 1, nx * upsample)
    j0 = np.floor(xi).astype(int)
    j1 = np.clip(j0 + 1, 0, nx - 1)
    wx = xi - j0
    return rows[:, j0] * (1 - wx) + rows[:, j1] * wx


def image_bounds(lats: np.ndarray, lons: np.ndarray) -> list[list[float]]:
    """MapLibre image-source corners (TL, TR, BR, BL) for cell-centre grids, half a cell out."""
    h = abs(lats[1] - lats[0]) / 2
    w = abs(lons[1] - lons[0]) / 2
    n, s, west, e = lats.max() + h, lats.min() - h, lons.min() - w, lons.max() + w
    return [[west, n], [e, n], [e, s], [west, s]]


def write_png(field: np.ndarray, lats: np.ndarray, path: Path, kind: str) -> None:
    rgba = _ramp(to_mercator_rows(field, lats), STOPS[kind])
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(path, optimize=True)


def legend(kind: str) -> dict:
    return {"kind": kind, "units": UNITS[kind], "stops": [{"value": v, "rgba": list(c)} for v, c in STOPS[kind]]}


def isobars(msl_hpa: np.ndarray, lats: np.ndarray, lons: np.ndarray, interval: float = 2.0) -> dict:
    """Ensemble-mean MSLP isobars as a GeoJSON FeatureCollection."""
    gen = contourpy.contour_generator(lons, lats, msl_hpa, line_type=contourpy.LineType.Separate)
    lo, hi = np.floor(np.nanmin(msl_hpa) / interval) * interval, np.ceil(np.nanmax(msl_hpa) / interval) * interval
    feats = []
    for lev in np.arange(lo, hi + interval, interval):
        for line in gen.lines(lev):
            if len(line) < 4:
                continue
            feats.append({"type": "Feature", "properties": {"hpa": float(lev)},
                          "geometry": {"type": "LineString", "coordinates": np.round(line, 3).tolist()}})
    return {"type": "FeatureCollection", "features": feats}


def write_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":"), allow_nan=False))
