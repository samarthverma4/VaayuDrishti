"""Download the ERA5 precipitation climate the EFI-proxy and SOT need for every event and the latest run.

    python -m pipeline.fetch_era5

Valid dates are the ends of each 24 h forecast window (00 UTC) for every cycle in data/events.yaml and
the latest processed run; each needs 30 years x 31 days of ERA5 fields (about 2.8 MB downloaded and
100 KB kept per day). Existing files are kept.
"""
from __future__ import annotations

import json
import logging

import pandas as pd

from pipeline import events as ev_mod
from pipeline.config import ARTIFACTS, MAX_LEAD_H
from pipeline.ingest import era5_clim


def valid_dates() -> set[pd.Timestamp]:
    inits = [i for e in ev_mod.load_events() for i in e.cycles]
    idx = ARTIFACTS / "index.json"
    if idx.exists() and (cur := json.loads(idx.read_text()).get("current")):
        inits.append(pd.Timestamp(cur["init"]))
    return {(i + pd.Timedelta(hours=h)).normalize() for i in inits for h in range(24, MAX_LEAD_H + 1, 24)}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    n = era5_clim.fetch(valid_dates())
    logging.info("ERA5 climate ready: %d days", n)


if __name__ == "__main__":
    main()
