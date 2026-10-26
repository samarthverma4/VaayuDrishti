"""District-level aggregation of ensemble rainfall and cyclone proximity.

Definitions shown in the UI:
- p_rain[k]: fraction of members in which at least one 0.25 degree grid cell in the district
  reaches IMD threshold k in the 24 h window ("anywhere in the district").
- rain_mm: 10th, 50th and 90th percentile across members of the district's highest cell total.
- p_strike: fraction of members whose cyclone track passes within 120 km of the district
  boundary during the window.
"""
from __future__ import annotations

import numpy as np
import shapely
from pyproj import Transformer

from pipeline import geo
from pipeline.definitions import RAIN_THRESHOLDS_MM, STRIKE_RADIUS_KM
from pipeline.ensemble import densify


def cell_index(lats: np.ndarray, lons: np.ndarray, bbox: dict) -> dict[str, np.ndarray]:
    """District id -> flat indices of grid cells whose centre lies in the district
    (nearest cell to the district's interior point when none does)."""
    d = geo.districts()
    d = d.cx[bbox["lon_min"]:bbox["lon_max"], bbox["lat_min"]:bbox["lat_max"]]
    glat, glon = np.meshgrid(lats, lons, indexing="ij")
    pts = shapely.points(glon.ravel(), glat.ravel())
    out = {}
    for r in d.itertuples():
        geom = r.geometry
        shapely.prepare(geom)
        idx = np.where(shapely.contains(geom, pts))[0]
        if len(idx) == 0:
            rp = geom.representative_point()
            i = int(np.argmin(np.abs(lats - rp.y)))
            j = int(np.argmin(np.abs(lons - rp.x)))
            if abs(lats[i] - rp.y) > 0.25 or abs(lons[j] - rp.x) > 0.25:
                continue
            idx = np.array([i * len(lons) + j])
        out[r.id] = idx
    return out


def rain_table(rain: np.ndarray, cells: dict[str, np.ndarray]) -> dict[str, dict]:
    """rain: (n_windows, member, lat, lon) mm."""
    flat = rain.reshape(rain.shape[0], rain.shape[1], -1)
    res = {}
    for did, idx in cells.items():
        dmax = flat[:, :, idx].max(axis=2)  # (window, member)
        res[did] = {
            "p_rain": {k: np.round((dmax >= thr).mean(axis=1), 3).tolist() for k, thr in RAIN_THRESHOLDS_MM.items()},
            "rain_mm": {q: np.round(np.percentile(dmax, p, axis=1), 1).tolist() for q, p in (("p10", 10), ("p50", 50), ("p90", 90))},
        }
    return res


def strike_table(members: list[dict], windows: list[tuple[int, int]], district_ids: list[str], center: tuple[float, float]) -> dict[str, list[float]]:
    """Fraction of members passing within STRIKE_RADIUS_KM of each district per window,
    measured in an azimuthal equidistant projection centred on the event."""
    tf = Transformer.from_crs("EPSG:4326", f"+proj=aeqd +lat_0={center[0]} +lon_0={center[1]} +units=km", always_xy=True)
    d = geo.districts().set_index("id").loc[district_ids]
    geoms = shapely.transform(d.geometry.values, lambda xy: np.column_stack(tf.transform(xy[:, 0], xy[:, 1])))
    shapely.prepare(geoms)
    hits = np.zeros((len(district_ids), len(windows)))
    n = 0
    for mem in members:
        n += 1
        if len(mem["points"]) == 0:
            continue
        s = densify(mem["points"])
        for w, (a, b) in enumerate(windows):
            sel = s[(s[:, 0] >= a) & (s[:, 0] < b)]
            if len(sel) == 0:
                continue
            x, y = tf.transform(sel[:, 2], sel[:, 1])
            line = shapely.linestrings(np.column_stack([x, y])) if len(sel) > 1 else shapely.points(x[0], y[0])
            hits[:, w] += shapely.dwithin(geoms, line, STRIKE_RADIUS_KM)
    p = hits / max(1, n)
    return {did: np.round(p[i], 3).tolist() for i, did in enumerate(district_ids)}


def build_table(rain: np.ndarray | None, windows: list[tuple[int, int]], cells: dict[str, np.ndarray],
                members: list[dict] | None, center: tuple[float, float], efi: np.ndarray | None = None) -> list[dict]:
    d = geo.districts().set_index("id")
    rt = rain_table(rain, cells) if rain is not None else {}
    ids = list(cells)
    st = strike_table(members, windows, ids, center) if members else {}
    rows = []
    for did in ids:
        r = rt.get(did, {})
        s = st.get(did)
        signal = max([max(v) for v in r.get("p_rain", {}).values()] + ([max(s)] if s else []) + [0])
        if signal <= 0:
            continue
        row = {"id": did, "name": d.loc[did, "name"], "state": d.loc[did, "state"], "p_strike": s, **r}
        if efi is not None:
            # highest EFI-proxy over the district's cells, per window
            row["efi_max"] = np.round(np.nan_to_num(efi.reshape(efi.shape[0], -1)[:, cells[did]].max(axis=1), nan=0.0), 2).tolist()
        rows.append(row)
    return rows
