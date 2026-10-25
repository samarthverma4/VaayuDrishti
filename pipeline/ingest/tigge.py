"""TIGGE GRIB2 loader (ECMWF Data Store downloads) for cases before the open archive starts.

Place files under data/raw/tigge/<event_id>/ (any names ending .grib/.grib2), containing
control (type=cf) and perturbed (type=pf) forecasts with: msl, 10u, 10v and tp
(total precipitation, accumulated from step 0). See README "Loading TIGGE data" for the
exact request. Returns the same normalized schema as ecmwf_ens.load, or None when the
files for that cycle are absent.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import xarray as xr

from pipeline.config import MAX_LEAD_H, RAW

log = logging.getLogger(__name__)
TIGGE_DIR = RAW / "tigge"


def _open(paths, type_: str, short: str) -> xr.DataArray | None:
    try:
        parts = [xr.open_dataset(p, engine="cfgrib", backend_kwargs={
            "filter_by_keys": {"dataType": type_, "shortName": short}, "indexpath": ""}) for p in paths]
    except Exception as exc:  # noqa: BLE001 - a file lacking this field is normal
        log.debug("cfgrib %s %s: %s", type_, short, exc)
        return None
    parts = [p for p in parts if p.data_vars]
    if not parts:
        return None
    ds = xr.combine_by_coords(parts, combine_attrs="drop_conflicts")
    da = ds[list(ds.data_vars)[0]]
    if "number" not in da.dims:
        da = da.expand_dims(number=[0])
    return da


def load(event_id: str, init: pd.Timestamp, bbox: dict) -> xr.Dataset | None:
    folder = TIGGE_DIR / event_id
    paths = sorted([*folder.glob("*.grib"), *folder.glob("*.grib2")]) if folder.exists() else []
    if not paths:
        return None
    try:
        import cfgrib  # noqa: F401
    except ImportError:
        log.warning("TIGGE files present but cfgrib is not installed: uv pip install -e '.[grib]'")
        return None
    fields = {}
    for short, name in (("msl", "msl"), ("10u", "u10"), ("10v", "v10"), ("tp", "tp")):
        arrs = [a for a in (_open(paths, "cf", short), _open(paths, "pf", short)) if a is not None]
        if not arrs:
            return None
        da = xr.concat(arrs, dim="number")
        if "time" in da.dims:
            if np.datetime64(init) not in da.time.values:
                return None
            da = da.sel(time=np.datetime64(init))
        fields[name] = da
    ds = xr.Dataset(fields)
    ds = ds.rename({"number": "member", "latitude": "lat", "longitude": "lon"})
    ds = ds.assign_coords(lead_h=("step", (ds.step.values / np.timedelta64(1, "h")).astype(int))).swap_dims({"step": "lead_h"})
    ds = ds.drop_vars([v for v in ("step", "time", "valid_time", "surface", "heightAboveGround", "meanSea") if v in ds.coords])
    ds = ds.sel(lead_h=ds.lead_h <= MAX_LEAD_H)
    if ds.lat.values[0] < ds.lat.values[-1]:
        ds = ds.isel(lat=slice(None, None, -1))
    ds = ds.sel(lat=slice(bbox["lat_max"], bbox["lat_min"]), lon=slice(bbox["lon_min"], bbox["lon_max"]))
    # tp is accumulated from step 0 (kg m-2); convert to the mean rate over each step
    dt = np.diff(ds.lead_h.values, prepend=ds.lead_h.values[0]) * 3600.0
    dtp = ds.tp.diff("lead_h", label="upper").reindex(lead_h=ds.lead_h)
    prate = dtp / xr.DataArray(np.where(dt > 0, dt, np.nan), dims="lead_h", coords={"lead_h": ds.lead_h})
    ds = ds.drop_vars("tp").assign(prate=prate.clip(min=0))
    ds = ds.transpose("lead_h", "member", "lat", "lon")
    ds.attrs.update(source="TIGGE (ECMWF Data Store)", licence="CC BY 4.0 (ECMWF) / CC BY-NC 4.0 (NCMRWF, IMD)",
                    init_time=init.isoformat(), model=f"TIGGE {event_id}")
    return ds.load()
