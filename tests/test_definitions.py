import numpy as np
import pandas as pd
import pytest

from pipeline.definitions import (
    destination, efi, haversine_km, imd_category, sot, spherical_mean, utc_to_ist_iso,
)

CLIM = np.linspace(0, 100, 99)  # climate quantiles at 1..99 %


def test_efi_is_bounded_and_signed():
    assert efi(np.full(51, 1000.0), CLIM) == pytest.approx(1.0, abs=0.05)  # all members beyond climate max
    assert efi(np.full(51, -1.0), CLIM) == pytest.approx(-1.0, abs=0.05)  # all members below climate min
    assert abs(efi(np.linspace(0, 100, 51), CLIM)) < 0.1  # ensemble distributed like climate
    rng = np.random.default_rng(0)
    for _ in range(20):
        assert -1 <= efi(rng.normal(50, 30, 51), CLIM) <= 1


def test_sot_sign():
    assert sot(np.full(51, 200.0), clim_q90=80, clim_q99=100) > 0  # 90th pct of ensemble above climate 99th
    assert sot(np.full(51, 10.0), clim_q90=80, clim_q99=100) < 0
    assert sot(np.full(51, 10.0), clim_q90=100, clim_q99=100) is None


def test_haversine_known_distance():
    # one degree of latitude ~ 111.2 km
    assert haversine_km(10, 80, 11, 80) == pytest.approx(111.2, abs=0.2)
    assert haversine_km(20, 85, 20, 85) == 0


def test_destination_roundtrip():
    lat, lon = destination(15.0, 88.0, 45.0, 120.0)
    assert haversine_km(15.0, 88.0, lat, lon) == pytest.approx(120.0, abs=0.01)


def test_spherical_mean_of_symmetric_points():
    lat, lon = spherical_mean([10, 10, 12, 12], [80, 82, 80, 82])
    assert lat == pytest.approx(11.0, abs=0.01) and lon == pytest.approx(81.0, abs=0.01)


@pytest.mark.parametrize("kt,code", [(10, None), (17, "D"), (30, "DD"), (34, "CS"), (50, "SCS"), (64, "VSCS"), (95, "ESCS"), (120, "SuCS")])
def test_imd_categories(kt, code):
    c = imd_category(kt)
    assert (c["code"] if c else None) == code


def test_ist_conversion():
    assert utc_to_ist_iso(pd.Timestamp("2024-10-24T21:00")) == "2024-10-25T02:30+05:30"


def test_efi_grid_matches_scalar_and_handles_dry_ties():
    from pipeline.definitions import efi_grid, sot_grid

    rng = np.random.default_rng(1)
    clim = rng.gamma(0.6, 15, (930, 40))
    clim[clim < 1] = 0  # many dry days, as in real rainfall climates
    ens = np.stack([rng.gamma(0.6, 15 * s, 51) for s in np.linspace(0.3, 6, 40)], axis=1)
    levels = np.linspace(0.01, 0.99, 99)
    scalar = [efi(ens[:, i], np.quantile(clim[:, i], levels)) for i in range(40)]
    assert np.allclose(efi_grid(ens, clim), scalar, atol=0.005)
    # wetter ensembles score higher
    g = efi_grid(ens, clim, dry_mm=0.0)
    assert g[-1] > 0.4 and g[0] < 0
    # members drawn from the climate itself: masking dry ties removes most of the bias
    same = clim[rng.choice(930, 51, replace=False)]
    assert abs(efi_grid(same, clim, dry_mm=0.0).mean()) < abs(efi_grid(same, clim).mean())
    s = sot_grid(ens, clim)
    assert s[-1] > s[0]
