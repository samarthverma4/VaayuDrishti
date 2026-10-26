"""IMD gridded daily rainfall, 0.25 degree (Pai et al. 2014, MAUSAM 65), from IMD Pune.

Files: data/raw/imd/rain_<year>.grd as served by https://imdpune.gov.in/cmpg/Griddata/Rainfall_25_Bin.html
(little-endian float32, day x 129 lat x 135 lon, 6.5-38.5 N, 66.5-100 E, -999 = no data / sea).
Day D holds the 24 h total ending 08:30 IST (03 UTC) on D. Checked on Fengal: the Puducherry cell
peaks on 2024-12-01, matching the record 24 h total observed at 08:30 IST on 1 December.

The analysis is interpolated from rain gauges over land only. pipeline.fetch_imd downloads the files.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.config import RAW

IMD_DIR = RAW / "imd"
LATS = np.round(np.arange(6.5, 38.5 + 1e-6, 0.25), 2)
LONS = np.round(np.arange(66.5, 100.0 + 1e-6, 0.25), 2)
DAY_END_UTC_H = 3
URL = "https://imdpune.gov.in/cmpg/Griddata/rainfall.php"
SOURCE = "IMD Pune gridded daily rainfall, 0.25° (Pai et al. 2014)"
FINAL_THROUGH = 2024  # IMD's NetCDF page (checked 2026-10-26) lists 1901-2024; later years appear only as binary downloads


def path(year: int) -> Path:
    return IMD_DIR / f"rain_{year}.grd"


@lru_cache(maxsize=4)
def _year(year: int) -> np.ndarray | None:
    p = path(year)
    if not p.exists():
        return None
    a = np.fromfile(p, "<f4")
    days = a.size // (LATS.size * LONS.size)
    expected = 366 if pd.Timestamp(f"{year}-12-31").dayofyear == 366 else 365
    if days * LATS.size * LONS.size != a.size or days != expected:
        raise ValueError(f"{p.name}: {a.size} values is not {expected} days of {LATS.size}x{LONS.size}")
    a = a.reshape(days, LATS.size, LONS.size)
    return np.where(a < -900, np.nan, a)


def day(date: pd.Timestamp) -> np.ndarray | None:
    """Observed 24 h rainfall (mm) ending 03 UTC on `date`, (lat ascending, lon), NaN off land. None if absent."""
    d = pd.Timestamp(date).normalize()
    a = _year(d.year)
    return None if a is None else a[d.dayofyear - 1]


def window_end(date: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(date).normalize() + pd.Timedelta(hours=DAY_END_UTC_H)


def provenance(year: int) -> dict:
    p = path(year)
    return {"file": f"data/raw/imd/{p.name}", "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "downloaded_at": pd.Timestamp(p.stat().st_mtime, unit="s").isoformat(), "source": SOURCE,
            "status": "in IMD's published 1901-2024 archive" if year <= FINAL_THROUGH else "binary download only, not yet in IMD's published 1901-2024 archive; may be revised",
            "url": "https://imdpune.gov.in/cmpg/Griddata/Rainfall_25_Bin.html"}
