"""TIGGE GRIB loader (ECMWF Data Store downloads) for cases before the open archive starts.

Files live in data/raw/tigge/<event_id>/<origin>_<cf|pf>_<yyyymm>.grib (pipeline.fetch_tigge writes them)
and hold control and perturbed forecasts of msl, 10u, 10v and tp (accumulated from step 0).

On first use each event is converted once: every field is read a single time, regridded when it comes
on ECMWF's reduced Gaussian grid (linear interpolation onto 0.25 degree, the grid used elsewhere in
VaayuDrishti), split by initial time and cached as Zarr in data/cache/tigge/. `load` then returns the same
normalised schema as ecmwf_ens.load, or None when that cycle is absent.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.spatial import Delaunay, cKDTree

from pipeline.config import CACHE, MAX_LEAD_H, RAW

log = logging.getLogger(__name__)
TIGGE_DIR = RAW / "tigge"
TIGGE_CACHE = CACHE / "tigge"
GRID_DEG = 0.25
FIELDS = (("msl", "msl"), ("10u", "u10"), ("10v", "v10"), ("tp", "tp"))
MODEL_NAMES = {"ecmwf": "ECMWF IFS ENS", "ncmrwf": "NCMRWF NEPS-G", "imd": "IMD GEFS"}


def _paths(event_id: str, origin: str) -> list[Path]:
    folder = TIGGE_DIR / event_id
    return sorted([*folder.glob(f"{origin}_*.grib"), *folder.glob(f"{origin}_*.grib2")]) if folder.exists() else []


def _open(paths, type_: str, short: str) -> xr.DataArray | None:
    parts = []
    for p in paths:
        try:
            ds = xr.open_dataset(p, engine="cfgrib", backend_kwargs={
                "filter_by_keys": {"dataType": type_, "shortName": short}, "indexpath": ""})
        except Exception as exc:  # noqa: BLE001 - a file lacking this field is normal
            log.debug("cfgrib %s %s %s: %s", p.name, type_, short, exc)
            continue
        if ds.data_vars:
            parts.append(ds)
    if not parts:
        return None
    ds = xr.combine_by_coords(parts, combine_attrs="drop_conflicts") if len(parts) > 1 else parts[0]
    da = ds[list(ds.data_vars)[0]]
    if "number" not in da.dims:
        da = da.expand_dims(number=[int(da.coords["number"]) if "number" in da.coords else 0])
    if "time" not in da.dims:
        da = da.expand_dims(time=[da.time.values])
    return da


class _Regridder:
    """Linear (barycentric) interpolation from scattered grid points to a regular lat/lon grid.
    Target points outside the source hull (box edges) take the nearest source value."""

    def __init__(self, src_lat, src_lon, lats, lons):
        glat, glon = np.meshgrid(lats, lons, indexing="ij")
        tri = Delaunay(np.column_stack([src_lon, src_lat]))
        target = np.column_stack([glon.ravel(), glat.ravel()])
        simplex = tri.find_simplex(target)
        self.valid = simplex >= 0
        T = tri.transform[simplex[self.valid]]
        b = np.einsum("nij,nj->ni", T[:, :2], target[self.valid] - T[:, 2])
        self.weights = np.column_stack([b, 1 - b.sum(axis=1)])
        self.vertices = tri.simplices[simplex[self.valid]]
        self.nearest = cKDTree(np.column_stack([src_lon, src_lat])).query(target[~self.valid])[1]
        self.shape = glat.shape

    def __call__(self, values: np.ndarray) -> np.ndarray:
        """values: (..., n_src) -> (..., ny, nx)"""
        out = np.full(values.shape[:-1] + (self.shape[0] * self.shape[1],), np.nan, np.float32)
        out[..., self.valid] = np.einsum("...nk,nk->...n", values[..., self.vertices], self.weights)
        out[..., ~self.valid] = values[..., self.nearest]
        return out.reshape(values.shape[:-1] + self.shape)


def _target_grid(bbox: dict) -> tuple[np.ndarray, np.ndarray]:
    lats = np.arange(bbox["lat_max"], bbox["lat_min"] - 1e-6, -GRID_DEG)
    lons = np.arange(bbox["lon_min"], bbox["lon_max"] + 1e-6, GRID_DEG)
    return lats, lons


def _cache_path(event_id: str, origin: str, init: pd.Timestamp) -> Path:
    return TIGGE_CACHE / event_id / f"{origin}_{init:%Y%m%dT%H}.zarr"


def prepare(event_id: str, bbox: dict, origin: str = "ecmwf") -> list[pd.Timestamp]:
    """Convert the event's GRIB files to one normalised Zarr per initial time. Returns the inits written."""
    paths = _paths(event_id, origin)
    if not paths:
        return []
    kinds = {}
    for p in paths:
        kind, month = p.stem.split("_")[1:3]
        kinds.setdefault(kind, set()).add(month)
    if kinds.get("cf") != kinds.get("pf"):
        # a partial download would otherwise be cached as a 1- or 50-member "ensemble"
        log.warning("%s %s: control and perturbed files do not cover the same months yet (%s); waiting for the download",
                    event_id, origin, {k: sorted(v) for k, v in kinds.items()})
        return []
    try:
        import cfgrib  # noqa: F401
    except ImportError:
        log.warning("TIGGE files present but cfgrib is not installed: uv pip install cfgrib eccodes eccodeslib")
        return []
    lats, lons = _target_grid(bbox)
    raw: dict[str, xr.DataArray] = {}
    for short, name in FIELDS:
        arrs = [a for a in (_open(paths, "cf", short), _open(paths, "pf", short)) if a is not None]
        if not arrs:
            log.warning("%s: no %s in %s", event_id, short, [p.name for p in paths])
            return []
        raw[name] = xr.concat(arrs, dim="number", join="inner") if len(arrs) > 1 else arrs[0]
    units_m = raw["tp"].attrs.get("units", raw["tp"].attrs.get("GRIB_units")) == "m"
    sample = raw["msl"]
    unstructured = "values" in sample.dims
    if unstructured:
        rg = _Regridder(sample.latitude.values, ((sample.longitude.values + 180) % 360) - 180, lats, lons)
    written = []
    for t in sample.time.values:
        init = pd.Timestamp(t)
        out = _cache_path(event_id, origin, init)
        if (out / "zarr.json").exists():
            written.append(init)
            continue
        data = {}
        for name, da in raw.items():
            da = da.sel(time=t)
            da = da.sel(step=da.step <= np.timedelta64(MAX_LEAD_H, "h")).transpose("step", "number", ...)
            vals = da.values.astype(np.float32)
            if unstructured:
                grid = rg(vals)
            else:
                d2 = da.assign_coords(longitude=((da.longitude + 180) % 360) - 180).sortby("longitude")
                if d2.latitude.values[0] < d2.latitude.values[-1]:
                    d2 = d2.isel(latitude=slice(None, None, -1))
                grid = d2.interp(latitude=lats, longitude=lons).values.astype(np.float32)
            data[name] = (("lead_h", "member", "lat", "lon"), grid)
        steps = (sample.sel(time=t).step.values / np.timedelta64(1, "h")).astype(int)
        steps = steps[steps <= MAX_LEAD_H]
        ds = xr.Dataset(data, coords={"lead_h": steps, "member": raw["msl"].number.values.astype(int), "lat": lats, "lon": lons})
        tp = ds.tp * (1000.0 if units_m else 1.0)  # TIGGE: kg m-2; ECMWF dissemination: metres
        dt = np.diff(steps, prepend=steps[0]) * 3600.0
        prate = tp.diff("lead_h", label="upper").reindex(lead_h=ds.lead_h) / xr.DataArray(
            np.where(dt > 0, dt, np.nan), dims="lead_h", coords={"lead_h": ds.lead_h})
        ds = ds.drop_vars("tp").assign(prate=prate.clip(min=0).astype(np.float32))
        ds.attrs.update(
            source=f"TIGGE {origin} (ECMWF Data Store)",
            licence="CC BY 4.0" if origin == "ecmwf" else "CC BY-NC 4.0",
            init_time=init.isoformat(), model=f"{MODEL_NAMES.get(origin, origin)} (TIGGE)",
            regridding="reduced Gaussian to 0.25 deg, linear" if unstructured else "regular grid interpolated to 0.25 deg",
            retrieved_at=pd.Timestamp(max(p.stat().st_mtime for p in paths), unit="s").isoformat(),
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        ds.to_zarr(out, mode="w", consolidated=False)
        written.append(init)
        log.info("%s %s: cached %s", event_id, origin, out.name)
    return written


def load(event_id: str, init: pd.Timestamp, bbox: dict, origin: str = "ecmwf") -> xr.Dataset | None:
    path = _cache_path(event_id, origin, init)
    if not (path / "zarr.json").exists():
        if init not in prepare(event_id, bbox, origin):
            return None
    return xr.open_zarr(path, consolidated=False).load()
