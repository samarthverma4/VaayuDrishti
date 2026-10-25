"""Tracker, ensemble statistics, rainfall accumulation and cross-cycle comparison on synthetic data."""
import numpy as np
import pandas as pd
import pytest
import xarray as xr

from pipeline.compare import compare
from pipeline.definitions import haversine_km
from pipeline.ensemble import strike_probability, summarize
from pipeline.fields import exceedance, rain_24h
from pipeline.track.cyclone import Tracker, seed_from_best_track

LEADS = np.array([0, 3, 6, 9, 12, 15, 18, 21, 24, 30, 36, 42, 48])
LATS = np.arange(25.0, 4.99, -0.25)
LONS = np.arange(80.0, 100.01, 0.25)
INIT = pd.Timestamp("2024-10-22")


def centre(lead, member):
    """A low moving north-west at ~0.1 deg/h, members offset slightly."""
    return 12.0 + 0.1 * lead * 0.7 + 0.02 * member, 92.0 - 0.1 * lead * 0.7


def synthetic(n_members=5):
    glat, glon = np.meshgrid(LATS, LONS, indexing="ij")
    msl = np.full((len(LEADS), n_members, len(LATS), len(LONS)), 101000.0, np.float32)
    for k, L in enumerate(LEADS):
        for m in range(n_members):
            la, lo = centre(L, m)
            d = haversine_km(la, lo, glat, glon)
            msl[k, m] -= 1500.0 * np.exp(-((d / 250.0) ** 2))  # 15 hPa deep low
    zeros = np.zeros_like(msl)
    prate = np.full_like(msl, 2.0 / 3600.0)  # 2 mm/h everywhere
    return xr.Dataset(
        {"msl": (("lead_h", "member", "lat", "lon"), msl), "u10": (("lead_h", "member", "lat", "lon"), zeros + 10),
         "v10": (("lead_h", "member", "lat", "lon"), zeros), "prate": (("lead_h", "member", "lat", "lon"), prate)},
        coords={"lead_h": LEADS, "member": np.arange(n_members), "lat": LATS, "lon": LONS},
    )


def best_track():
    times = INIT + pd.to_timedelta(LEADS, unit="h")
    pos = [centre(L, 0) for L in LEADS]
    return pd.DataFrame({"time": times, "lat": [p[0] for p in pos], "lon": [p[1] for p in pos], "wind_kt": 40.0})


def test_tracker_follows_synthetic_low():
    ds = synthetic()
    k0, seed = seed_from_best_track(INIT, ds.lead_h.values, best_track())
    assert k0 == 0
    tracks = Tracker(ds).track_all(k0, seed)
    for m, pts in tracks.items():
        assert len(pts) == len(LEADS), f"member {m} lost the low"
        for p in pts:
            la, lo = centre(p.lead_h, m)
            assert haversine_km(p.lat, p.lon, la, lo) < 20  # sub-grid refinement
            assert p.depth_hpa > 5


def test_tracker_rejects_flat_field():
    ds = synthetic()
    ds["msl"][:] = 101000.0
    tracks = Tracker(ds).track_all(0, (12.0, 92.0))
    assert all(len(p) == 0 for p in tracks.values())


def test_summary_mean_spread_and_strike():
    ds = synthetic()
    tracks = Tracker(ds).track_all(0, (12.0, 92.0))
    s = summarize(tracks, LEADS, INIT)
    assert s["n_members"] == 5 and len(s["mean"]) == len(LEADS)
    assert all(p["n_members"] == 5 for p in s["mean"])
    assert s["mean"][0]["spread_km"] < 20
    sp = strike_probability(s["members"], LATS, LONS, [(0, 49)])
    i, j = np.argmin(abs(LATS - 12.0)), np.argmin(abs(LONS - 92.0))
    assert sp[0, i, j] == pytest.approx(1.0)  # every member passes over the start point
    assert sp[0, 0, 0] == 0.0  # far corner never struck


def test_rain_accumulation_and_exceedance():
    rain, windows = rain_24h(synthetic())
    assert windows == [(0, 24), (24, 48)]
    assert np.allclose(rain, 48.0)  # 2 mm/h x 24 h
    p = exceedance(rain * 2)  # 96 mm: heavy yes, very heavy no
    assert np.all(p["heavy"] == 1.0) and np.all(p["very_heavy"] == 0.0)


def _tracks(init, shift):
    mean = [{"lead_h": L, "valid_time": (init + pd.Timedelta(hours=L)).isoformat(), "lat": 15.0 + shift, "lon": 85.0, "spread_km": 50.0}
            for L in (0, 24, 48)]
    return {"init": init.isoformat(), "mean": mean, "landfall": None}


def test_compare_only_matches_identical_valid_times():
    a = _tracks(pd.Timestamp("2024-10-21"), 0.0)
    b = _tracks(pd.Timestamp("2024-10-22"), 1.0)
    res = compare(a, b)
    assert res["matched_valid_times"] == 2  # 22 Oct 00 and 23 Oct 00 only
    assert all(r["displacement_km"] == pytest.approx(111.2, abs=0.5) for r in res["by_valid_time"])
    with pytest.raises(ValueError):
        compare(a, a)
