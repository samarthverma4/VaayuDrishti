"""Cross-cycle comparison (Forecast Stability Lens). Only compares matching valid times."""
from __future__ import annotations

import pandas as pd

from pipeline.definitions import haversine_km


def compare(a: dict, b: dict, districts_a: list[dict] | None = None, districts_b: list[dict] | None = None,
            threshold_key: str = "very_heavy", p_min: float = 0.3) -> dict:
    """a, b: tracks.json payloads of two cycles of the same event (a earlier than b)."""
    ia, ib = pd.Timestamp(a["init"]), pd.Timestamp(b["init"])
    if ia == ib:
        raise ValueError("cycles must differ")
    if ia > ib:
        a, b, districts_a, districts_b = b, a, districts_b, districts_a
        ia, ib = ib, ia
    ma = {p["valid_time"]: p for p in a["mean"]}
    mb = {p["valid_time"]: p for p in b["mean"]}
    common = sorted(set(ma) & set(mb))
    rows = []
    for vt in common:
        pa, pb = ma[vt], mb[vt]
        rows.append({
            "valid_time": vt,
            "lead_a_h": pa["lead_h"], "lead_b_h": pb["lead_h"],
            "displacement_km": round(float(haversine_km(pa["lat"], pa["lon"], pb["lat"], pb["lon"])), 1),
            "spread_change_km": round(pb["spread_km"] - pa["spread_km"], 1),
            "a": {"lat": pa["lat"], "lon": pa["lon"]}, "b": {"lat": pb["lat"], "lon": pb["lon"]},
        })
    landfall = None
    la, lb = a.get("landfall"), b.get("landfall")
    if la and lb:
        landfall = {
            "shift_km": round(float(haversine_km(la["mean_lat"], la["mean_lon"], lb["mean_lat"], lb["mean_lon"])), 1),
            "time_change_h": round((pd.Timestamp(lb["median_time"]) - pd.Timestamp(la["median_time"])) / pd.Timedelta(hours=1), 1),
            "fraction_change": round(lb["fraction"] - la["fraction"], 3),
        }
    district_change = None
    if districts_a is not None and districts_b is not None:
        def above(rows, init):
            # windows are relative to each cycle's init; compare on absolute valid days
            s = {}
            for r in rows:
                for w, p in enumerate(r.get("p_rain", {}).get(threshold_key, [])):
                    if p >= p_min:
                        day = (init + pd.Timedelta(hours=24 * (w + 1))).isoformat()
                        s.setdefault(r["id"], []).append(day)
            return s
        sa, sb = above(districts_a, ia), above(districts_b, ib)
        district_change = {
            "threshold": threshold_key, "p_min": p_min,
            "added": sorted(set(sb) - set(sa)), "removed": sorted(set(sa) - set(sb)), "kept": sorted(set(sa) & set(sb)),
        }
    return {
        "cycle_a": ia.isoformat(), "cycle_b": ib.isoformat(),
        "matched_valid_times": len(rows),
        "by_valid_time": rows,
        "landfall": landfall,
        "districts": district_change,
        "note": "VaayuDrishti diagnostic, not an official index. Positions compared only at identical valid times.",
    }
