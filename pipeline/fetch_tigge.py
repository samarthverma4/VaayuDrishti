"""Download TIGGE ensemble forecasts from the ECMWF Data Store (ECDS) for the 2023 case studies.

Credentials: put your ECDS personal access token in ~/.ecdsapirc as

    url: https://ecds.ecmwf.int/api
    key: <PERSONAL-ACCESS-TOKEN>

(a separate file so an existing ~/.cdsapirc for the Climate Data Store is not touched), then:

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
RC = Path.home() / ".ecdsapirc"
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


def client():
    import cdsapi

    if not RC.exists():
        raise SystemExit(f"Missing {RC}. Create it with your ECDS token (see the module docstring).")
    cfg = yaml.safe_load(RC.read_text())
    return cdsapi.Client(url=cfg["url"], key=cfg["key"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("event_ids", nargs="*")
    ap.add_argument("--origin", default="ecmwf", choices=["ecmwf", "ncmrwf", "imd"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

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
