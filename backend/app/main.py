"""VYOMTRA API: read-only over precomputed artifacts, plus CAP draft generation.

Run: uvicorn backend.app.main:app --port 8000
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pipeline import cap
from pipeline.compare import compare as compare_cycles
from pipeline.config import ARTIFACTS, ROOT

API = "/api/v1"
DISCLAIMER = "Experimental decision-support guidance. Not an official IMD warning."
CYCLE_RE = re.compile(r"^(\d{10}|domain|system-\d+)$")
ID_RE = re.compile(r"^[a-z0-9-]+$")

app = FastAPI(
    title="VYOMTRA API",
    version="1.0.0",
    description="Ensemble-aware extreme-weather intelligence for India. " + DISCLAIMER,
    docs_url=f"{API}/docs",
    openapi_url=f"{API}/openapi.json",
)
app.add_middleware(GZipMiddleware, minimum_size=2048)


class Problem(HTTPException):
    def __init__(self, status: int, what: str, why: str, can_still: str | None = None):
        super().__init__(status, {"missing": what, "why": why, "available": can_still})


@lru_cache(maxsize=512)
def _read(path: str, mtime: float):
    return json.loads(Path(path).read_text())


def read_json(path: Path, what: str, why: str):
    if not path.exists():
        raise Problem(404, what, why, "GET /api/v1/events lists what is available")
    return _read(str(path), path.stat().st_mtime)


def index() -> dict:
    return read_json(ARTIFACTS / "index.json", "artifact index",
                     "The pipeline has not been run. Run: python -m pipeline.fetch && python -m pipeline.build")


def _check_id(v: str, kind: str) -> str:
    if not ID_RE.match(v):
        raise Problem(400, kind, f"'{v}' is not a valid {kind} id")
    return v


def cycle_dir(event_id: str, cycle: str) -> Path:
    _check_id(event_id, "event")
    if not CYCLE_RE.match(cycle):
        raise Problem(400, "cycle", f"'{cycle}' is not a cycle id (YYYYMMDDHH, 'domain' or 'system-N')")
    if event_id == "current":
        cur = index().get("current")
        if not cur:
            raise Problem(404, "current forecast", "No current run has been processed", "Historical replays are available")
        d = ARTIFACTS / "current" / pd.Timestamp(cur["init"]).strftime("%Y%m%d%H") / cycle
        if not d.exists():
            raise Problem(404, f"current-forecast part {cycle}", "Not produced for the latest run", "GET /api/v1/current lists the parts")
        return d
    ev = ARTIFACTS / "events" / event_id
    if not ev.exists():
        raise Problem(404, f"event {event_id}", "Unknown event or not built yet", "GET /api/v1/events lists what is available")
    if not (ev / cycle).exists():
        raise Problem(404, f"cycle {cycle} of {event_id}", "This forecast cycle has not been processed (see the event's cycle list for the reason)",
                      f"GET /api/v1/events/{event_id}/cycles")
    return ev / cycle


def provenance(event_id: str, cycle: str) -> dict:
    return read_json(cycle_dir(event_id, cycle) / "provenance.json", "provenance",
                     f"Cycle {cycle} of {event_id} has not been processed")


def respond(payload: dict, prov: dict | None = None) -> JSONResponse:
    body = {**payload, "disclaimer": DISCLAIMER}
    if prov is not None:
        body["provenance"] = prov
    return JSONResponse(body)


# ---- endpoints ---------------------------------------------------------------------------

@app.get(f"{API}/health")
def health():
    idx = (ARTIFACTS / "index.json")
    return {"status": "ok", "artifacts": idx.exists(),
            "generated_at": json.loads(idx.read_text())["generated_at"] if idx.exists() else None}


@app.get(f"{API}/sources")
def sources():
    return respond({"sources": index()["sources"]})


@app.get(f"{API}/events")
def list_events():
    idx = index()
    return respond({"generated_at": idx["generated_at"], "events": idx["events"], "current": idx.get("current")})


@app.get(f"{API}/events/{{event_id}}")
def get_event(event_id: str):
    _check_id(event_id, "event")
    if event_id == "current":
        return respond(index().get("current") or {})
    return respond(read_json(ARTIFACTS / "events" / event_id / "event.json", f"event {event_id}",
                             "Unknown event or not built yet"))


@app.get(f"{API}/events/{{event_id}}/cycles")
def get_cycles(event_id: str):
    ev = get_event(event_id)
    data = json.loads(ev.body)
    return respond({"event": event_id, "cycles": data.get("cycles", data.get("systems", []))})


def _cycle_file(event_id: str, cycle: str, name: str, what: str, why: str) -> JSONResponse:
    data = read_json(cycle_dir(event_id, cycle) / name, what, why)
    return respond(data if isinstance(data, dict) else {"data": data}, provenance(event_id, cycle))


@app.get(f"{API}/events/{{event_id}}/cycles/{{cycle}}/tracks")
def get_tracks(event_id: str, cycle: str):
    return _cycle_file(event_id, cycle, "tracks.json", "ensemble tracks",
                       "No cyclone was seeded in this cycle (the storm had not formed within the forecast window)")


@app.get(f"{API}/events/{{event_id}}/cycles/{{cycle}}/fields")
def get_fields(event_id: str, cycle: str):
    d = cycle_dir(event_id, cycle)
    data = read_json(d / "fields.json", "gridded fields", "Cycle not processed")
    base = f"{API}/assets/{d.relative_to(ARTIFACTS).as_posix()}/"
    layers = {k: [base + p for p in v] for k, v in data["layers"].items()}
    return respond({**data, "layers": layers}, provenance(event_id, cycle))


@app.get(f"{API}/events/{{event_id}}/cycles/{{cycle}}/isobars")
def get_isobars(event_id: str, cycle: str, lead_h: int | None = None):
    data = read_json(cycle_dir(event_id, cycle) / "isobars.json", "isobars", "Cycle not processed")
    if lead_h is not None:
        if str(lead_h) not in data:
            raise Problem(404, f"isobars at T+{lead_h}", "Isobars are stored every 6 h", f"Available leads: {', '.join(list(data)[:6])}…")
        data = {str(lead_h): data[str(lead_h)]}
    return respond({"isobars": data, "definition": "Ensemble-mean MSLP every 2 hPa"}, provenance(event_id, cycle))


@app.get(f"{API}/events/{{event_id}}/cycles/{{cycle}}/districts")
def get_districts(event_id: str, cycle: str,
                  hazard: Literal["heavy", "very_heavy", "extremely_heavy", "strike"] | None = None,
                  window: int | None = Query(None, ge=0), min_p: float = Query(0.0, ge=0, le=1)):
    """All districts with any ensemble signal; with `hazard`, filtered and sorted by its probability."""
    data = read_json(cycle_dir(event_id, cycle) / "districts.json", "district table", "Cycle not processed")
    if hazard is None:
        return respond({"windows": data["windows"], "hazard": None, "rows": data["rows"],
                        "definitions": data["definitions"]}, provenance(event_id, cycle))
    rows = []
    for r in data["rows"]:
        series = r["p_strike"] if hazard == "strike" else r.get("p_rain", {}).get(hazard)
        if not series:
            continue
        p = max(series) if window is None else (series[window] if window < len(series) else 0)
        if p >= min_p and p > 0:
            rows.append({**r, "p": p})
    rows.sort(key=lambda r: -r["p"])
    return respond({"windows": data["windows"], "hazard": hazard, "window": window, "rows": rows,
                    "definitions": data["definitions"]}, provenance(event_id, cycle))


@app.get(f"{API}/events/{{event_id}}/cycles/{{cycle}}/verification")
def get_verification(event_id: str, cycle: str):
    return _cycle_file(event_id, cycle, "verification.json", "verification",
                       "Not yet evaluated: verification needs an observed best track and a seeded forecast track")


@app.get(f"{API}/events/{{event_id}}/compare")
def get_compare(event_id: str, a: str, b: str,
                hazard: Literal["heavy", "very_heavy", "extremely_heavy"] = "very_heavy", p_min: float = Query(0.3, ge=0, le=1)):
    ta = read_json(cycle_dir(event_id, a) / "tracks.json", f"tracks for {a}", "Cycle has no tracks")
    tb = read_json(cycle_dir(event_id, b) / "tracks.json", f"tracks for {b}", "Cycle has no tracks")
    da = read_json(cycle_dir(event_id, a) / "districts.json", "districts", "Cycle not processed")["rows"]
    db = read_json(cycle_dir(event_id, b) / "districts.json", "districts", "Cycle not processed")["rows"]
    try:
        res = compare_cycles(ta, tb, da, db, hazard, p_min)
    except ValueError as exc:
        raise Problem(400, "comparison", str(exc))
    return respond(res)


@app.get(f"{API}/current")
def current():
    cur = index().get("current")
    if not cur:
        raise Problem(404, "current forecast", "No current run processed. Run: python -m pipeline.fetch --latest && python -m pipeline.build --current",
                      "Historical replays")
    return respond(cur)


@lru_cache
def _district_index() -> list[dict]:
    return json.loads((ARTIFACTS / "geo" / "districts_index.json").read_text())


@app.get(f"{API}/districts")
def search_districts(q: str = Query("", max_length=60), limit: int = Query(20, le=100)):
    ql = q.strip().lower()
    hits = [d for d in _district_index() if ql in d["name"].lower() or ql in d["state"].lower()] if ql else _district_index()
    hits.sort(key=lambda d: (not d["name"].lower().startswith(ql), d["name"]))
    return respond({"query": q, "results": hits[:limit], "source": "geoBoundaries IND ADM2 (lgdirectory.gov.in, 2021)"})


@app.get(f"{API}/districts/{{district_id}}/risk")
def district_risk(district_id: str, event: str, cycle: str):
    _check_id(district_id.replace("--", "-"), "district")
    data = read_json(cycle_dir(event, cycle) / "districts.json", "district table", "Cycle not processed")
    row = next((r for r in data["rows"] if r["id"] == district_id), None)
    meta = next((d for d in _district_index() if d["id"] == district_id), None)
    if meta is None:
        raise Problem(404, f"district {district_id}", "Unknown district id", "GET /api/v1/districts?q=")
    trend = None
    ev = json.loads(get_event(event).body)
    cycles = [c["init"] for c in ev.get("cycles", []) if c.get("status") == "ready"]
    this = pd.Timestamp(f"{cycle[:8]}T{cycle[8:]}") if cycle.isdigit() else None
    prev = [c for c in cycles if this is not None and pd.Timestamp(c) < this]
    if prev and row:
        pdir = cycle_dir(event, pd.Timestamp(prev[-1]).strftime("%Y%m%d%H"))
        pdata = read_json(pdir / "districts.json", "previous cycle", "not processed")
        prow = next((r for r in pdata["rows"] if r["id"] == district_id), None)
        def peak(r, k):
            s = (r or {}).get("p_rain", {}).get(k) if k != "strike" else (r or {}).get("p_strike")
            return max(s) if s else 0.0
        trend = {"previous_cycle": prev[-1],
                 "change": {k: round(peak(row, k) - peak(prow, k), 3) for k in ("heavy", "very_heavy", "extremely_heavy", "strike")}}
    return respond({"district": meta, "risk": row, "no_signal": row is None, "windows": data["windows"],
                    "trend_vs_previous_cycle": trend, "definitions": data["definitions"]}, provenance(event, cycle))


class AdvisoryRequest(BaseModel):
    event_id: str = Field(pattern=r"^[a-z0-9-]+$")
    cycle: str = Field(pattern=r"^(\d{10}|domain|system-\d+)$")
    hazard: Literal["heavy", "very_heavy", "extremely_heavy", "strike"]
    window: int = Field(ge=0)
    district_ids: list[str] = Field(min_length=1, max_length=40)


@app.post(f"{API}/advisories/draft")
def advisory_draft(req: AdvisoryRequest):
    prov = provenance(req.event_id, req.cycle)
    data = read_json(cycle_dir(req.event_id, req.cycle) / "districts.json", "district table", "Cycle not processed")
    if req.window >= len(data["windows"]):
        raise Problem(400, "window", f"Cycle has {len(data['windows'])} windows")
    rows = {r["id"]: r for r in data["rows"]}
    sel = []
    for did in req.district_ids:
        r = rows.get(did)
        if r is None:
            raise Problem(400, f"district {did}", "No ensemble signal for this district in this cycle; it cannot be included in an advisory")
        series = r["p_strike"] if req.hazard == "strike" else r["p_rain"][req.hazard]
        sel.append({"id": did, "name": r["name"], "state": r["state"], "p": float(series[req.window]) if series else 0.0})
    if req.event_id == "current":
        ev = {"id": "current", "name": "current forecast"}
    else:
        e = json.loads(get_event(req.event_id).body)
        ev = {"id": e["id"], "name": e["name"]}
    w = data["windows"][req.window]
    xml, report = cap.build(ev, prov["init_time"], "cyclone" if req.hazard == "strike" else req.hazard,
                            (w["start_h"], w["end_h"]), sel, {"source": prov["source"], "members": prov["members"]})
    return respond({"cap_xml": xml, "validation": report, "districts": sel, "window": w,
                    "label": cap.DISCLAIMER}, prov)


# ---- static assets and the built frontend -------------------------------------------------

app.mount(f"{API}/assets", StaticFiles(directory=ARTIFACTS, check_dir=False), name="assets")

DIST = ROOT / "frontend" / "dist"


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        raise Problem(404, path, "Unknown API route", f"See {API}/docs")
    f = DIST / path
    if path and f.is_file() and DIST in f.resolve().parents:
        return FileResponse(f)
    if (DIST / "index.html").exists():
        return FileResponse(DIST / "index.html")
    return JSONResponse({"message": "Frontend not built. Run: cd frontend && npm run build", "api_docs": f"{API}/docs"})
