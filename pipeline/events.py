"""Event registry: storms from data/events.yaml, with dates, region and forecast cycles
derived from IBTrACS so nothing about an event is hand-typed."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import yaml

from pipeline.config import DATA, DOMAIN
from pipeline.ingest import ibtracs

MAX_CYCLES = 7
REGION_PAD_DEG = 8.0
ARCHIVE_START = pd.Timestamp("2024-04-01")


@dataclass
class Event:
    id: str
    sid: str
    name: str
    basin: str
    ensemble_source: str
    track: pd.DataFrame = field(repr=False)
    landfall: dict | None
    bbox: dict
    cycles: list[pd.Timestamp]

    @property
    def start(self) -> pd.Timestamp:
        return self.track.time.min()

    @property
    def end(self) -> pd.Timestamp:
        return self.track.time.max()


def _bbox(track: pd.DataFrame) -> dict:
    def snap(x, f):
        return float(f(x * 4) / 4)

    return {
        "lat_min": max(DOMAIN["lat_min"], snap(track.lat.min() - REGION_PAD_DEG, np.floor)),
        "lat_max": min(DOMAIN["lat_max"], snap(track.lat.max() + REGION_PAD_DEG, np.ceil)),
        "lon_min": max(DOMAIN["lon_min"], snap(track.lon.min() - REGION_PAD_DEG, np.floor)),
        "lon_max": min(DOMAIN["lon_max"], snap(track.lon.max() + REGION_PAD_DEG, np.ceil)),
    }


def _cycles(track: pd.DataFrame, landfall: dict | None) -> list[pd.Timestamp]:
    """Daily 00 UTC runs from the day before the first fix up to the last run before landfall
    (or before peak intensity for storms that never landfall)."""
    first = track.time.min().normalize() - pd.Timedelta(days=1)
    if landfall:
        last = pd.Timestamp(landfall["time"]).floor("D")
        if last == pd.Timestamp(landfall["time"]):
            last -= pd.Timedelta(days=1)
    else:
        last = track.loc[track.wind_kt.idxmax(), "time"].floor("D") if track.wind_kt.notna().any() else track.time.max().floor("D")
    days = pd.date_range(first, last, freq="D")
    return list(days[-MAX_CYCLES:])


def load_events() -> list[Event]:
    cfg = yaml.safe_load((DATA / "events.yaml").read_text())["events"]
    out = []
    for e in cfg:
        track = ibtracs.best_track(e["sid"])
        lf = ibtracs.landfall(track)
        cycles = _cycles(track, lf)
        if e["ensemble_source"] == "ecmwf-ifs-ens":
            cycles = [c for c in cycles if c >= ARCHIVE_START]
        out.append(
            Event(
                id=e["id"], sid=e["sid"], name=e["name"], basin=e["basin"],
                ensemble_source=e["ensemble_source"], track=track, landfall=lf,
                bbox=_bbox(track), cycles=cycles,
            )
        )
    return out


def get(event_id: str) -> Event:
    for e in load_events():
        if e.id == event_id:
            return e
    raise LookupError(event_id)
