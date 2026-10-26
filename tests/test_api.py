"""API contract tests. They need built artifacts (python -m pipeline.build); skipped otherwise."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from pipeline.config import ARTIFACTS

pytestmark = pytest.mark.skipif(not (ARTIFACTS / "index.json").exists(), reason="artifacts not built")
client = TestClient(app)


def first_ready():
    for e in json.loads((ARTIFACTS / "index.json").read_text())["events"]:
        for c in e["cycles"]:
            if c["status"] == "ready" and c.get("has_tracks"):
                return e["id"], c["init"][:13].replace("-", "").replace("T", "")
    pytest.skip("no ready cycle")


def test_events_and_disclaimer():
    r = client.get("/api/v1/events")
    assert r.status_code == 200
    body = r.json()
    assert "Not an official IMD warning" in body["disclaimer"]
    assert body["events"]


@pytest.mark.parametrize("part", ["tracks", "fields", "districts", "verification", "isobars"])
def test_cycle_endpoints_carry_provenance(part):
    ev, cyc = first_ready()
    r = client.get(f"/api/v1/events/{ev}/cycles/{cyc}/{part}")
    assert r.status_code == 200, r.text
    prov = r.json()["provenance"]
    assert prov["members"] > 0 and prov["init_time"] and prov["source"]


def test_unknown_event_is_descriptive_404():
    r = client.get("/api/v1/events/no-such-storm/cycles/2024102200/tracks")
    assert r.status_code == 404
    assert r.json()["detail"]["missing"] == "event no-such-storm"


def test_bad_ids_rejected():
    assert client.get("/api/v1/events/..%2Fetc/cycles/x/tracks").status_code in (400, 404)
    assert client.get("/api/v1/events/dana-2024/cycles/../../tracks").status_code in (400, 404)


def test_tigge_event_reports_missing_cycles():
    e = client.get("/api/v1/events/biparjoy-2023").json()
    assert e["cycles_ready"] == 0
    assert all(c["status"] == "missing" and "TIGGE" in c["reason"] for c in e["cycles"])


def test_cap_draft_validates_against_schema():
    ev, cyc = first_ready()
    rows = client.get(f"/api/v1/events/{ev}/cycles/{cyc}/districts?hazard=heavy&min_p=0.01").json()["rows"]
    if not rows:
        pytest.skip("no district signal")
    r = client.post("/api/v1/advisories/draft", json={"event_id": ev, "cycle": cyc, "hazard": "heavy", "window": 0,
                                                       "district_ids": [rows[0]["id"]]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["validation"]["valid"], d["validation"]["errors"]
    assert "<status>Draft</status>" in d["cap_xml"]
    assert "Not an Official IMD Warning" in d["cap_xml"]


def test_cap_rejects_district_without_signal():
    ev, cyc = first_ready()
    r = client.post("/api/v1/advisories/draft", json={"event_id": ev, "cycle": cyc, "hazard": "heavy", "window": 0,
                                                       "district_ids": ["ladakh--leh"]})
    assert r.status_code == 400


def test_compare_endpoint():
    e = client.get("/api/v1/events/dana-2024").json()
    ready = [c["init"][:13].replace("-", "").replace("T", "") for c in e["cycles"] if c["status"] == "ready"]
    if len(ready) < 2:
        pytest.skip("needs two cycles")
    r = client.get(f"/api/v1/events/dana-2024/compare?a={ready[0]}&b={ready[1]}")
    assert r.status_code == 200
    assert r.json()["matched_valid_times"] > 0


def test_district_search():
    r = client.get("/api/v1/districts?q=puri")
    assert any(d["name"] == "Puri" for d in r.json()["results"])


def test_tigge_snapshot_matches_source_file():
    """A single-field snapshot keeps its file provenance and makes no forecast claims."""
    import hashlib
    from pipeline.config import ROOT

    r = client.get("/api/v1/events/biparjoy-2023/snapshots")
    if r.status_code == 404:
        pytest.skip("no TIGGE snapshot built")
    for s in r.json()["snapshots"]:
        prov = s["provenance"]
        path = ROOT / prov["file"]
        assert path.exists() and path.stat().st_size == prov["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == prov["sha256"]
        assert prov["grib"]["shortName"] == "msl" and str(prov["grib"]["stepRange"]) == "0"
        lo, hi = s["field_range_hpa"]
        assert lo == s["model_min"]["msl_hpa"] and lo < hi
        assert s["isobars"]["features"] and "not_available" in s
        assert "tracks" not in s and "members" not in s


def test_snapshot_missing_is_descriptive_404():
    r = client.get("/api/v1/events/no-such-storm/snapshots")
    assert r.status_code == 404
