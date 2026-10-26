"""TIGGE loader on real ECMWF GRIB2 (ECMWF open data, 25 Oct 2026 00 UTC, members 1-3, T+0..24).

Fetch the probe once with:
    from ecmwf.opendata import Client
    Client(source="ecmwf").retrieve(date="2026-10-25", time=0, stream="enfo", type="pf", number=[1, 2, 3],
        param=["msl", "10u", "10v", "tp"], step=[0, 6, 12, 18, 24],
        target="data/raw/tigge/_probe/ecmwf_pf_probe.grib")
"""
import pandas as pd
import pytest

from pipeline.config import RAW
from pipeline.fields import rain_24h

PROBE = RAW / "tigge" / "_probe" / "ecmwf_pf_probe.grib"
pytestmark = pytest.mark.skipif(not PROBE.exists(), reason="probe GRIB not downloaded")
INIT = pd.Timestamp("2026-10-25T00")
BBOX = {"lat_min": 5, "lat_max": 30, "lon_min": 75, "lon_max": 100}


def test_loader_normalises_schema_and_units():
    from pipeline.ingest import tigge

    ds = tigge.load("_probe", INIT, BBOX)
    assert list(ds.dims) == ["lead_h", "member", "lat", "lon"]
    assert list(ds.member.values) == [1, 2, 3]
    assert ds.lat.values[0] == 30 and ds.lon.values[0] == 75
    assert 95000 < float(ds.msl.min()) < 101000  # Pa
    rain, _ = rain_24h(ds)
    assert 50 < float(rain.max()) < 1000  # mm in 24 h near the Bay of Bengal low, not metres


def test_loader_refuses_wrong_init_or_origin():
    from pipeline.ingest import tigge

    assert tigge.load("_probe", INIT - pd.Timedelta(days=1), BBOX) is None
    assert tigge.load("_probe", INIT, BBOX, origin="ncmrwf") is None
