"""IBTrACS v04r01 best tracks for the North Indian basin (NOAA NCEI)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

from pipeline.config import IBTRACS_NI_URL, RAW

PATH = RAW / "ibtracs.NI.list.v04r01.csv"


def download(force: bool = False) -> Path:
    if PATH.exists() and not force:
        return PATH
    r = requests.get(IBTRACS_NI_URL, timeout=120)
    r.raise_for_status()
    PATH.write_bytes(r.content)
    return PATH


def load_all() -> pd.DataFrame:
    download()
    df = pd.read_csv(PATH, skiprows=[1], low_memory=False, keep_default_na=False)
    df["time"] = pd.to_datetime(df["ISO_TIME"])
    for c in ("LAT", "LON", "NEWDELHI_WIND", "NEWDELHI_PRES", "WMO_WIND", "WMO_PRES", "DIST2LAND"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def best_track(sid: str) -> pd.DataFrame:
    """One storm's fixes: time, lat, lon, wind_kt and pres_hpa from RSMC New Delhi where present."""
    df = load_all()
    t = df[df["SID"] == sid].copy()
    if t.empty:
        raise LookupError(f"storm {sid} not in IBTrACS NI")
    t["wind_kt"] = t["NEWDELHI_WIND"].fillna(t["WMO_WIND"])
    t["pres_hpa"] = t["NEWDELHI_PRES"].fillna(t["WMO_PRES"])
    t["agency"] = "RSMC New Delhi (IMD) via IBTrACS"
    t["landfall"] = t["LANDFALL"].astype(str)
    return t[["time", "LAT", "LON", "wind_kt", "pres_hpa", "DIST2LAND", "NATURE"]].rename(
        columns={"LAT": "lat", "LON": "lon", "DIST2LAND": "dist2land_km", "NATURE": "nature"}
    ).reset_index(drop=True)


def landfall(track: pd.DataFrame) -> dict | None:
    """First transition from sea to land (DIST2LAND reaches 0), linearly interpolated in time."""
    over_land = track["dist2land_km"] <= 0
    if not over_land.any():
        return None
    i = int(over_land.values.argmax())
    if i == 0:
        row = track.iloc[0]
        return {"time": row.time.isoformat(), "lat": float(row.lat), "lon": float(row.lon)}
    a, b = track.iloc[i - 1], track.iloc[i]
    da, db = float(a.dist2land_km), float(b.dist2land_km)
    f = da / (da - db) if da != db else 1.0
    t = a.time + (b.time - a.time) * f
    return {
        "time": t.isoformat(),
        "lat": float(a.lat + (b.lat - a.lat) * f),
        "lon": float(a.lon + (b.lon - a.lon) * f),
    }
