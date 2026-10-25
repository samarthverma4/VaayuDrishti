"""Download and cache every forecast run the case studies need.

    python -m pipeline.fetch                 # all events
    python -m pipeline.fetch dana-2024       # one event
    python -m pipeline.fetch --latest        # newest run over the whole domain
"""
from __future__ import annotations

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from pipeline import events
from pipeline.config import DOMAIN
from pipeline.ingest import ecmwf_ens

log = logging.getLogger("fetch")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("event_ids", nargs="*")
    ap.add_argument("--latest", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ds = ecmwf_ens.open_archive()
    jobs = []
    if args.latest:
        jobs.append((ecmwf_ens.available_inits(ds)[-1], DOMAIN))
    else:
        for ev in events.load_events():
            if args.event_ids and ev.id not in args.event_ids:
                continue
            if ev.ensemble_source != "ecmwf-ifs-ens":
                log.info("%s: ensemble source %s is not fetched automatically", ev.id, ev.ensemble_source)
                continue
            log.info("%s: %d cycles, bbox %s", ev.id, len(ev.cycles), ev.bbox)
            jobs += [(c, ev.bbox) for c in ev.cycles]

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(ecmwf_ens.fetch, init, bbox, ds): (init, bbox) for init, bbox in jobs}
        for i, f in enumerate(as_completed(futs), 1):
            init, bbox = futs[f]
            try:
                log.info("[%d/%d] ok %s -> %s", i, len(jobs), init, f.result().name)
            except Exception as exc:
                log.error("[%d/%d] failed %s: %s", i, len(jobs), init, exc)


if __name__ == "__main__":
    main()
