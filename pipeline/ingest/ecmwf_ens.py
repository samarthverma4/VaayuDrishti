"""ECMWF IFS ENS forecasts from the dynamical.org Icechunk archive (ECMWF open data, CC BY 4.0).

The archive holds 00 UTC runs from 2024-04-01, 51 members, 0.25 degree, 3-hourly to T+144
then 6-hourly. Each (init, region) is cached locally as a Zarr store so the pipeline and the
demo never depend on the network after the first fetch.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import icechunk
import numpy as np
import pandas as pd
import xarray as xr

from pipeline.config import CACHE, DYNAMICAL_ENS, ENS_VARS, MAX_LEAD_H

log = logging.getLogger(__name__)

SOURCE_ID = "ecmwf-ifs-ens"


def open_archive() -> xr.Dataset:
    storage = icechunk.s3_storage(
        bucket=DYNAMICAL_ENS["bucket"],
        prefix=DYNAMICAL_ENS["prefix"],
        region=DYNAMICAL_ENS["region"],
        anonymous=True,
    )
    repo = icechunk.Repository.open(storage)
    return xr.open_zarr(repo.readonly_session("main").store, chunks=None)


def available_inits(ds: xr.Dataset | None = None) -> pd.DatetimeIndex:
    ds = ds if ds is not None else open_archive()
    return pd.DatetimeIndex(ds.init_time.values)


def cache_path(init: pd.Timestamp, bbox: dict) -> Path:
    tag = f"{bbox['lat_min']:g}_{bbox['lat_max']:g}_{bbox['lon_min']:g}_{bbox['lon_max']:g}"
    return CACHE / SOURCE_ID / f"{init:%Y%m%dT%H}_{tag}.zarr"


def _read_var(ds: xr.Dataset, name: str, init: pd.Timestamp, bbox: dict) -> xr.DataArray:
    da = ds[ENS_VARS[name]].sel(
        init_time=init,
        latitude=slice(bbox["lat_max"], bbox["lat_min"]),
        longitude=slice(bbox["lon_min"], bbox["lon_max"]),
        lead_time=slice(np.timedelta64(0, "h"), np.timedelta64(MAX_LEAD_H, "h")),
    )
    for attempt in range(4):
        try:
            return da.load().rename(name)
        except Exception as exc:  # network hiccups on S3 range reads
            log.warning("read %s %s failed (%s), retry %d", name, init, exc, attempt + 1)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"could not read {name} for {init}")


def fetch(init: pd.Timestamp, bbox: dict, ds: xr.Dataset | None = None) -> Path:
    """Fetch one forecast run for a region into the local cache. Returns the cache path."""
    out = cache_path(init, bbox)
    if (out / "zarr.json").exists():
        return out
    ds = ds if ds is not None else open_archive()
    if init not in available_inits(ds):
        raise LookupError(f"init {init} not in archive")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=len(ENS_VARS)) as pool:
        arrays = list(pool.map(lambda n: _read_var(ds, n, init, bbox), ENS_VARS))
    merged = xr.merge(arrays, compat="override", join="exact").drop_vars("init_time", errors="ignore")
    for v in merged.variables.values():
        v.encoding = {}  # drop the archive's chunk/shard layout; it does not fit the subset
    merged = merged.assign_coords(lead_h=("lead_time", (merged.lead_time.values / np.timedelta64(1, "h")).astype(int)))
    merged = merged.swap_dims({"lead_time": "lead_h"}).drop_vars("lead_time")
    merged = merged.rename({"ensemble_member": "member", "latitude": "lat", "longitude": "lon"})
    merged.attrs.update(
        source="ECMWF IFS ENS via dynamical.org (ECMWF Open Data)",
        licence="CC BY 4.0",
        init_time=init.isoformat(),
        retrieved_at=pd.Timestamp.utcnow().isoformat(),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp.zarr")
    merged.to_zarr(tmp, mode="w", consolidated=False)
    tmp.rename(out)
    log.info("fetched %s %s in %.0fs", init, bbox, time.time() - t0)
    return out


def load(init: pd.Timestamp, bbox: dict) -> xr.Dataset:
    """Normalized dataset: dims (lead_h, member, lat, lon); msl Pa, u10/v10 m/s, prate kg m-2 s-1."""
    return xr.open_zarr(cache_path(init, bbox), consolidated=False).load()
