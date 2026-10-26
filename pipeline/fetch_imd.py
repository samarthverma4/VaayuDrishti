"""Download IMD gridded daily rainfall (0.25 degree) for the years the case studies need.

    python -m pipeline.fetch_imd            # years spanned by data/events.yaml
    python -m pipeline.fetch_imd 2024 2025  # explicit years

Existing files are kept; a file is only written after it downloads completely and has the expected size.
"""
from __future__ import annotations

import logging
import sys
import urllib.parse
import urllib.request

import pandas as pd

from pipeline import events as ev_mod
from pipeline.ingest.imd_rain import IMD_DIR, LATS, LONS, URL, path

log = logging.getLogger(__name__)


def fetch(year: int) -> None:
    out = path(year)
    if out.exists():
        log.info("have %s", out.name)
        return
    days = pd.Timestamp(f"{year}-12-31").dayofyear
    expected = days * LATS.size * LONS.size * 4
    IMD_DIR.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL, data=urllib.parse.urlencode({"rain": str(year)}).encode(), method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        content = r.read()
    if len(content) != expected:
        raise RuntimeError(f"IMD {year}: got {len(content)} bytes, expected {expected} (year may be incomplete)")
    tmp = out.with_suffix(".part")
    tmp.write_bytes(content)
    tmp.rename(out)
    log.info("saved %s (%.1f MB)", out.name, len(content) / 1e6)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    years = [int(a) for a in sys.argv[1:]] or sorted({y for e in ev_mod.load_events() for y in (e.start.year, e.end.year)})
    for y in years:
        fetch(y)


if __name__ == "__main__":
    main()
