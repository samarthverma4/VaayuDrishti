"""Rainfall verification maths on synthetic fields (no data files needed)."""
import numpy as np
import pandas as pd
import xarray as xr

from pipeline import rain_verify as rv


def test_fss_perfect_and_disjoint():
    valid = np.ones((20, 20), bool)
    a = np.zeros((20, 20)); a[5:8, 5:8] = 1
    assert rv.fss(a, a, valid, 1) == 1.0
    b = np.zeros((20, 20)); b[14:17, 14:17] = 1
    assert rv.fss(a, b, valid, 1) == 0.0
    # a small displacement scores higher with a larger neighbourhood
    c = np.zeros((20, 20)); c[6:9, 6:9] = 1
    assert rv.fss(a, c, valid, 1) < rv.fss(a, c, valid, 5)
    assert rv.fss(np.zeros((20, 20)), np.zeros((20, 20)), valid, 3) is None


def test_contingency_counts():
    obs = np.full((4, 4), np.nan); obs[:2, :] = [[100, 0, 100, 0], [0, 0, 0, 0]]
    members = np.zeros((4, 4, 4))
    members[:, 0, 0] = 100            # all members: hit
    members[:3, 0, 1] = 100           # 3 of 4: false alarm
    members[:1, 0, 2] = 100           # 1 of 4: below the 50% rule, so a miss
    s = rv.score_day(members, obs)["thresholds"]["heavy"]
    assert (s["hits"], s["misses"], s["false_alarms"]) == (1, 1, 1)
    assert s["pod"] == 0.5 and s["far"] == 0.5 and abs(s["csi"] - 1 / 3) < 1e-3
    assert rv.score_day(members, obs)["n_cells"] == 8  # NaN cells are not scored


def test_alignment_requires_exact_steps():
    leads = np.r_[np.arange(0, 145, 3), np.arange(150, 241, 6)]
    assert rv._aligned(leads, 3, 27) and rv._aligned(leads, 99, 123)
    assert not rv._aligned(leads, 123, 147)  # 147 h is not an output step


def test_member_accumulation_window():
    leads = np.arange(0, 49, 3)
    pr = np.full((leads.size, 2, 1, 1), 1 / 3600.0, np.float32)  # 1 mm per hour
    ds = xr.Dataset({"prate": (("lead_h", "member", "lat", "lon"), pr)}, coords={"lead_h": leads})
    assert np.allclose(rv._member_accum(ds, 3, 27), 24.0)


def test_storm_region_radius():
    track = pd.DataFrame({"time": pd.to_datetime(["2024-01-01 00:00", "2024-01-02 00:00"]),
                          "lat": [15.0, 15.0], "lon": [80.0, 80.0], "wind_kt": [50.0, 50.0]})
    lats = np.arange(20, 10, -0.25); lons = np.arange(75, 85, 0.25)
    m = rv.storm_region(track, pd.Timestamp("2024-01-01 03:00"), pd.Timestamp("2024-01-01 12:00"), lats, lons)
    assert m[np.argmin(abs(lats - 15)), np.argmin(abs(lons - 80))]
    assert not m[np.argmin(abs(lats - 19.5)), np.argmin(abs(lons - 80))]  # about 500 km away
    assert rv.storm_region(track, pd.Timestamp("2024-02-01"), pd.Timestamp("2024-02-02"), lats, lons) is None
