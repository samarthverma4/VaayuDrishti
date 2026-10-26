"""EFI-proxy wiring: climate sampling dates and per-window output."""
import numpy as np
import pandas as pd

from pipeline import extremes
from pipeline.ingest import era5_clim


def test_climate_days_span_30_years_and_31_days():
    days = era5_clim.climate_days(pd.Timestamp("2024-10-25"))
    assert len(days) == 30 * 31
    assert min(days) == pd.Timestamp("1993-10-10") and max(days) == pd.Timestamp("2022-11-09")
    leap = era5_clim.climate_days(pd.Timestamp("2024-02-29"))  # non-leap years centre on 28 Feb
    assert len(leap) == 30 * 31


def test_for_cycle_uses_climate_per_window(monkeypatch):
    lats = np.array([15.0, 14.75]); lons = np.array([80.0, 80.25, 80.5])
    clim = np.random.default_rng(0).gamma(0.8, 10, (930, 2, 3)).astype(np.float32)
    calls = []

    def fake(valid, la, lo):
        calls.append(pd.Timestamp(valid))
        return clim

    monkeypatch.setattr(era5_clim, "climate", fake)
    rain = np.zeros((2, 51, 2, 3), np.float32); rain[1] = 500.0  # day 2 far beyond climate
    out = extremes.for_cycle(rain, [(0, 24), (24, 48)], pd.Timestamp("2024-10-24"), lats, lons)
    assert calls == [pd.Timestamp("2024-10-25"), pd.Timestamp("2024-10-26")]
    assert out["efi"].shape == (2, 2, 3)
    assert (out["efi"][1] > 0.95).all() and (out["efi"][0] <= 0).all()
    assert out["valid_dates"] == ["2024-10-25", "2024-10-26"]


def test_for_cycle_needs_complete_climate(monkeypatch):
    monkeypatch.setattr(era5_clim, "climate", lambda *a: None)
    rain = np.zeros((1, 51, 2, 2), np.float32)
    assert extremes.for_cycle(rain, [(0, 24)], pd.Timestamp("2024-10-24"), np.array([1.0, 0.75]), np.array([80.0, 80.25])) is None
