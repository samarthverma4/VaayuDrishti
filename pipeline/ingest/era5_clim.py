"""ERA5 24 h precipitation climate for the EFI-proxy and SOT.

Source: ERA5 total precipitation accumulated over the 24 h ending at 00 UTC, 0.25 degree, from the
WeatherBench 2 public copy on Google Cloud (gs://weatherbench2, no account needed). Checked: the value at
time T equals the sum of ERA5 hourly precipitation for the hours ending T-23 .. T, i.e. the window (T-24 h, T],
the same convention as VaayuDrishti's forecast windows from 00 UTC runs.

Each day is stored once, cropped to the analysis domain, as data/raw/era5/tp24_00z/YYYYMMDD.npy (mm,
latitude descending on the 0.25 degree lattice). The climate for a valid date D pools CLIM_YEARS at
D-15 .. D+15 days (30 years x 31 days = 930 samples per cell).
"""
from __future__ import annotations

import json
import logging
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.config import DOMAIN, RAW

log = logging.getLogger(__name__)
STORE = "https://storage.googleapis.com/weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr"
VAR = "total_precipitation_24hr"
ERA5_DIR = RAW / "era5" / "tp24_00z"
CLIM_YEARS = range(1993, 2023)
HALF_WINDOW_D = 15
T0 = pd.Timestamp("1959-01-01")
GLOBAL_LATS = np.round(np.arange(90, -90.001, -0.25), 2)
GLOBAL_LONS = np.round(np.arange(0, 360, 0.25), 2)
LATS = np.round(np.arange(DOMAIN["lat_max"], DOMAIN["lat_min"] - 1e-6, -0.25), 2)
LONS = np.round(np.arange(DOMAIN["lon_min"], DOMAIN["lon_max"] + 1e-6, 0.25), 2)
SOURCE = "ERA5 (ECMWF / Copernicus C3S) via WeatherBench 2, 24 h precipitation ending 00 UTC, 0.25°"
LICENCE = "Copernicus licence (free use with attribution)"


def path(day: pd.Timestamp) -> Path:
    return ERA5_DIR / f"{day:%Y%m%d}.npy"


def _fetch(day: pd.Timestamp) -> None:
    from numcodecs import Blosc

    out = path(day)
    if out.exists():
        return
    i = int((day - T0) / pd.Timedelta(hours=6))
    for attempt in range(5):
        try:
            raw = urllib.request.urlopen(f"{STORE}/{VAR}/{i}.0.0", timeout=120).read()
            break
        except OSError as exc:  # timeouts and connection resets: back off and retry
            if attempt == 4:
                raise RuntimeError(f"ERA5 {day:%Y-%m-%d}: {exc}") from exc
            time.sleep(5 * 2 ** attempt)
    g = np.frombuffer(Blosc().decode(raw), "<f4").reshape(GLOBAL_LATS.size, GLOBAL_LONS.size)
    iy = np.searchsorted(-GLOBAL_LATS, -LATS)
    ix = np.searchsorted(GLOBAL_LONS, LONS)
    crop = (g[np.ix_(iy, ix)] * 1000.0).astype(np.float32)  # m -> mm
    tmp = out.with_suffix(".part.npy")
    np.save(tmp, crop)
    tmp.rename(out)


def climate_days(valid: pd.Timestamp) -> list[pd.Timestamp]:
    """Days pooled for the climate of `valid` (00 UTC dates)."""
    out = []
    for y in CLIM_YEARS:
        try:
            centre = pd.Timestamp(year=y, month=valid.month, day=valid.day)
        except ValueError:  # 29 Feb in a non-leap year
            centre = pd.Timestamp(year=y, month=2, day=28)
        out += [centre + pd.Timedelta(days=k) for k in range(-HALF_WINDOW_D, HALF_WINDOW_D + 1)]
    return out


def fetch(valid_days, workers: int = 16) -> int:
    """Download every climate day needed for the given valid dates. Returns the number of files present."""
    ERA5_DIR.mkdir(parents=True, exist_ok=True)
    days = sorted({d for v in valid_days for d in climate_days(pd.Timestamp(v).normalize())})
    todo = [d for d in days if not path(d).exists()]
    log.info("ERA5 climate: %d days needed, %d to download", len(days), len(todo))
    done, failed = 0, []

    def one(d):
        try:
            _fetch(d)
        except RuntimeError as exc:
            return str(exc)

    with ThreadPoolExecutor(workers) as ex:
        for err in ex.map(one, todo):
            done += 1
            if err:
                failed.append(err)
                log.warning(err)
            if done % 200 == 0:
                log.info("ERA5 climate: %d / %d", done, len(todo))
    if failed:
        raise RuntimeError(f"{len(failed)} ERA5 days failed after retries; rerun to fetch them")
    (ERA5_DIR.parent / "provenance.json").write_text(json.dumps({
        "source": SOURCE, "store": STORE, "variable": VAR, "licence": LICENCE, "years": [CLIM_YEARS.start, CLIM_YEARS.stop - 1],
        "half_window_days": HALF_WINDOW_D, "files": len(list(ERA5_DIR.glob("*.npy"))),
        "updated_at": pd.Timestamp.utcnow().tz_localize(None).isoformat()}, indent=1))
    return len(days)


def climate(valid: pd.Timestamp, lats: np.ndarray, lons: np.ndarray) -> np.ndarray | None:
    """Climate samples (n_days, lat, lon) in mm for `valid` on the given 0.25 degree sub-grid; None if incomplete."""
    days = climate_days(pd.Timestamp(valid).normalize())
    if not all(path(d).exists() for d in days):
        return None
    iy = np.round((LATS[0] - lats) / 0.25).astype(int)
    ix = np.round((lons - LONS[0]) / 0.25).astype(int)
    if iy.min() < 0 or iy.max() >= LATS.size or ix.min() < 0 or ix.max() >= LONS.size:
        return None
    return np.stack([np.load(path(d), mmap_mode="r")[np.ix_(iy, ix)] for d in days])
