"""EFI-proxy and Shift of Tails for 24 h rainfall, against an ERA5 climate.

ECMWF's operational EFI compares the ensemble with the model's own reforecast climate. Those
reforecasts are not open, so VaayuDrishti uses ERA5 (30 years, +-15 days) instead: an "EFI-proxy". Model
and reanalysis rainfall differ in bias, so the proxy shows where the forecast is unusual relative to
the reanalysis record, not the operational product.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.definitions import efi_grid, sot_grid
from pipeline.ingest import era5_clim

DRY_MM = 0.1  # climate quantiles at or below this are treated as dry days (see efi_grid)

DEFINITIONS = {
    "efi": "EFI-proxy for 24 h rain: how far the whole ensemble distribution sits above the ERA5 climate "
           f"({era5_clim.CLIM_YEARS.start}-{era5_clim.CLIM_YEARS.stop - 1}, ±{era5_clim.HALF_WINDOW_D} days) for the cell and date. "
           "0 = like climate, 1 = every member beyond the climate maximum; 0.5 is commonly read as unusual, 0.8 as very unusual. "
           "Not a probability. Dry-day climate quantiles are left out of the integral.",
    "sot": "Shift of Tails for 24 h rain: > 0 when the ensemble's 90th percentile exceeds the ERA5 climate's 99th; "
           "larger values mean a more extreme tail. Shown where the climate's 90th and 99th percentiles differ by at least 0.1 mm.",
}


def for_cycle(rain: np.ndarray, windows: list[tuple[int, int]], init: pd.Timestamp,
              lats: np.ndarray, lons: np.ndarray) -> dict | None:
    """rain: (window, member, lat, lon) mm. Returns {'efi': (W, lat, lon), 'sot': ..., 'valid_dates': [...]}
    or None when the ERA5 climate is missing for any window."""
    efi = np.full((len(windows), lats.size, lons.size), np.nan, np.float32)
    sot = np.full_like(efi, np.nan)
    dates = []
    for w, (_, b) in enumerate(windows):
        end = init + pd.Timedelta(hours=b)
        if end.hour != 0:
            return None
        clim = era5_clim.climate(end, lats, lons)
        if clim is None:
            return None
        ens = rain[w].reshape(rain.shape[1], -1)
        c = clim.reshape(clim.shape[0], -1)
        efi[w] = efi_grid(ens, c, dry_mm=DRY_MM).reshape(lats.size, lons.size)
        sot[w] = sot_grid(ens, c).reshape(lats.size, lons.size)
        dates.append(end.date().isoformat())
    return {"efi": efi, "sot": sot, "valid_dates": dates}
