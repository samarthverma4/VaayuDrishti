"""Download TIGGE ensemble forecasts from the ECMWF Data Store (ECDS) for the 2023 case studies.

Credentials, first match wins:
  1. CDSAPI_URL and CDSAPI_KEY environment variables
  2. ~/.ecdsapirc (useful if ~/.cdsapirc is already used for the Climate Data Store)
  3. ~/.cdsapirc, the cdsapi default, when its url points at https://ecds.ecmwf.int/api
Each file holds two lines: `url: https://ecds.ecmwf.int/api` and `key: <PERSONAL-ACCESS-TOKEN>`.

    python -m pipeline.fetch_tigge --probe              # one tiny request to test access
    python -m pipeline.fetch_tigge --dry-run            # print the requests only
    python -m pipeline.fetch_tigge                      # ECMWF ENS for every TIGGE event
    python -m pipeline.fetch_tigge biparjoy-2023 --origin ncmrwf   # NEPS-G (CC BY-NC 4.0)

One request per event, origin and forecast type; files land in data/raw/tigge/<event>/<origin>_<type>.grib.
Requests are queued by ECDS and can take from minutes to hours.
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import yaml

from pipeline import events
from pipeline.ingest.tigge import TIGGE_DIR

log = logging.getLogger("fetch_tigge")
ECDS_URL = "https://ecds.ecmwf.int/api"
RC_FILES = [Path.home() / ".ecdsapirc", Path.home() / ".cdsapirc"]
LEADS_H = [str(h) for h in range(0, 241, 6)]
VARIABLES = ["mean_sea_level_pressure", "10_m_u_component_of_wind", "10_m_v_component_of_wind", "total_precipitation"]
FORECAST_TYPES = {"cf": "control_forecast", "pf": "perturbed_forecast"}


def requests_for(ev: events.Event, origin: str) -> list[tuple[Path, dict]]:
    days = sorted(ev.cycles)
    years = sorted({f"{d:%Y}" for d in days})
    months = sorted({f"{d:%m}" for d in days})
    if len(years) > 1 or len(months) > 1:
        # cycles crossing a month boundary (Michaung: 29 Nov to 4 Dec) need one request per month,
        # otherwise year x month x day would also fetch unwanted dates
        groups = {}
        for d in days:
            groups.setdefault((f"{d:%Y}", f"{d:%m}"), []).append(f"{d:%d}")
    else:
        groups = {(years[0], months[0]): [f"{d:%d}" for d in days]}
    b = ev.bbox
    out = []
    for (y, m), dd in groups.items():
        for short, ftype in FORECAST_TYPES.items():
            req = {
                "origin": origin,
                "forecast_type": ftype,
                "level_type": "single_level",
                "variable": VARIABLES,
                "year": [y],
                "month": [m],
                "day": dd,
                "time": ["00:00"],
                "leadtime_hour": LEADS_H,
                "area": [b["lat_max"], b["lon_min"], b["lat_min"], b["lon_max"]],  # N, W, S, E
                "data_format": "grib",
            }
            out.append((TIGGE_DIR / ev.id / f"{origin}_{short}_{y}{m}.grib", req))
    return out


def credentials() -> tuple[str, str, str]:
    """(url, key, where-from). Never logs the key."""
    import os

    if os.environ.get("CDSAPI_URL", "").startswith(ECDS_URL) and os.environ.get("CDSAPI_KEY"):
        return os.environ["CDSAPI_URL"], os.environ["CDSAPI_KEY"], "environment"
    for rc in RC_FILES:
        if not rc.exists():
            continue
        cfg = yaml.safe_load(rc.read_text()) or {}
        if str(cfg.get("url", "")).rstrip("/").startswith(ECDS_URL) and cfg.get("key"):
            return str(cfg["url"]), str(cfg["key"]), str(rc)
        log.info("%s does not point at %s; skipping it", rc, ECDS_URL)
    raise SystemExit(f"No ECDS credentials found in CDSAPI_URL/CDSAPI_KEY, {RC_FILES[0]} or {RC_FILES[1]} (see the module docstring).")


def client():
    import cdsapi

    url, key, where = credentials()
    log.info("using ECDS credentials from %s", where)
    return cdsapi.Client(url=url, key=key)


PROBE = {  # smallest useful request: Biparjoy control forecast, one field, one step, small box
    "origin": "ecmwf", "forecast_type": "control_forecast", "level_type": "single_level",
    "variable": ["mean_sea_level_pressure"], "year": ["2023"], "month": ["06"], "day": ["12"],
    "time": ["00:00"], "leadtime_hour": ["0"], "area": [25, 60, 10, 75], "data_format": "grib",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("event_ids", nargs="*")
    ap.add_argument("--origin", default="ecmwf", choices=["ecmwf", "ncmrwf", "imd"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--probe", action="store_true", help="submit one tiny request to check access")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.probe:
        path = TIGGE_DIR / "_access_probe" / "ecmwf_cf_probe.grib"
        path.parent.mkdir(parents=True, exist_ok=True)
        client().retrieve("tigge-forecasts", PROBE, str(path))
        log.info("probe OK: %s (%d bytes)", path, path.stat().st_size)
        return

    todo = []
    for ev in events.load_events():
        if ev.ensemble_source != "tigge" or (args.event_ids and ev.id not in args.event_ids):
            continue
        todo += requests_for(ev, args.origin)
    if args.dry_run:
        for path, req in todo:
            print(path.relative_to(TIGGE_DIR.parent.parent.parent), yaml.safe_dump(req, default_flow_style=None, sort_keys=False), sep="\n")
        return
    c = client()
    for path, req in todo:
        if path.exists() and path.stat().st_size > 0:
            log.info("have %s", path.name)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        log.info("requesting %s (queued at ECDS; this can take a while)", path)
        c.retrieve("tigge-forecasts", req, str(path))
        log.info("saved %s (%.1f MB)", path, path.stat().st_size / 1e6)


if __name__ == "__main__":
    main()
