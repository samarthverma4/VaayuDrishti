"""CAP 1.2 advisory drafts. Status is always "Draft": a template for an authorized issuer,
never an actionable public warning. Output is validated against the OASIS CAP 1.2 schema."""
from __future__ import annotations

import uuid
from functools import lru_cache

import pandas as pd
import shapely
from lxml import etree

from pipeline import geo
from pipeline.config import RAW
from pipeline.definitions import IST_OFFSET_H, RAIN_LABELS

NS = "urn:oasis:names:tc:emergency:cap:1.2"
DISCLAIMER = "Experimental Decision-Support Guidance. Not an Official IMD Warning."
SENDER = "vyomtra-draft@localhost"


@lru_cache
def schema() -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(str(RAW / "geo" / "CAP-v1.2.xsd")))


def _cap_time(ts: pd.Timestamp) -> str:
    ist = ts.tz_localize(None) + pd.Timedelta(hours=IST_OFFSET_H) if ts.tzinfo else ts + pd.Timedelta(hours=IST_OFFSET_H)
    return ist.strftime("%Y-%m-%dT%H:%M:%S") + "+05:30"


def _certainty(p: float) -> str:
    if p >= 0.5:
        return "Likely"
    if p > 0.05:
        return "Possible"
    return "Unlikely"


def _severity(hazard_key: str) -> str:
    return {"heavy": "Moderate", "very_heavy": "Severe", "extremely_heavy": "Extreme", "cyclone": "Severe"}.get(hazard_key, "Unknown")


def _polygon(did: str) -> str | None:
    g = geo.districts().set_index("id").loc[did, "geometry"]
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda p: p.area)
    g = shapely.simplify(g, 0.01)
    ring = list(g.exterior.coords)
    if len(ring) > 200:
        g = shapely.simplify(g, 0.03)
        ring = list(g.exterior.coords)
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return " ".join(f"{lat:.4f},{lon:.4f}" for lon, lat in ring)


def _sub(parent, tag, text=None):
    el = etree.SubElement(parent, f"{{{NS}}}{tag}")
    if text is not None:
        el.text = str(text)
    return el


def build(event: dict, cycle: str, hazard_key: str, window: tuple[int, int], districts: list[dict],
          provenance: dict, now: pd.Timestamp | None = None) -> tuple[str, dict]:
    """districts: rows with id, name, state and `p` (probability for this hazard and window)."""
    if not districts:
        raise ValueError("select at least one district")
    now = now or pd.Timestamp.utcnow().tz_localize(None)
    init = pd.Timestamp(cycle)
    onset, expires = init + pd.Timedelta(hours=window[0]), init + pd.Timedelta(hours=window[1])
    pmax = max(d["p"] for d in districts)
    label = RAIN_LABELS.get(hazard_key, "Cyclone track proximity (within 120 km)")
    ident = f"vyomtra-{event['id']}-{init:%Y%m%d%H}-{hazard_key}-{uuid.uuid4().hex[:8]}"

    root = etree.Element(f"{{{NS}}}alert", nsmap={None: NS})
    _sub(root, "identifier", ident)
    _sub(root, "sender", SENDER)
    _sub(root, "sent", _cap_time(now))
    _sub(root, "status", "Draft")
    _sub(root, "msgType", "Alert")
    _sub(root, "source", "VYOMTRA decision-support prototype")
    _sub(root, "scope", "Private")
    _sub(root, "addresses", "authorized-forecaster")
    _sub(root, "note", f"{DISCLAIMER} Generated from {provenance['source']}, cycle {init:%Y-%m-%d %H} UTC, {provenance['members']} members.")
    info = _sub(root, "info")
    _sub(info, "language", "en-IN")
    _sub(info, "category", "Met")
    _sub(info, "event", label if hazard_key != "cyclone" else f"Cyclone {event['name']} track proximity")
    _sub(info, "responseType", "Monitor")
    _sub(info, "urgency", "Future")
    _sub(info, "severity", _severity(hazard_key))
    _sub(info, "certainty", _certainty(pmax))
    _sub(info, "onset", _cap_time(onset))
    _sub(info, "expires", _cap_time(expires))
    _sub(info, "senderName", "VYOMTRA (experimental, non-official)")
    _sub(info, "headline", f"DRAFT: Ensemble guidance for {label.split(' (')[0].lower()} ({event['name']})")
    names = ", ".join(f"{d['name']} ({d['state']})" for d in districts)
    _sub(info, "description",
         f"{DISCLAIMER} ECMWF ensemble guidance from the {init:%d %b %Y %H} UTC cycle indicates a probability of up to "
         f"{pmax:.0%} for: {label}, between {onset:%d %b %H:%M} and {expires:%d %b %H:%M} UTC, in {names}. "
         "Probability is the fraction of ensemble members meeting the condition. Verify against IMD bulletins before any use.")
    _sub(info, "instruction", "For review by an authorized forecaster only. Do not disseminate to the public.")
    for name, value in (("probability_max", f"{pmax:.3f}"), ("ensemble_members", provenance["members"]),
                        ("forecast_cycle_utc", f"{init:%Y-%m-%dT%H:%M:%SZ}"), ("data_source", provenance["source"])):
        p = _sub(info, "parameter")
        _sub(p, "valueName", name)
        _sub(p, "value", value)
    for d in districts:
        area = _sub(info, "area")
        _sub(area, "areaDesc", f"{d['name']}, {d['state']} (probability {d['p']:.0%})")
        poly = _polygon(d["id"])
        if poly:
            _sub(area, "polygon", poly)

    xml = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode()
    sch = schema()
    valid = sch.validate(etree.fromstring(xml.encode()))
    report = {"valid": bool(valid), "errors": [str(e) for e in sch.error_log], "schema": "OASIS CAP 1.2", "identifier": ident}
    return xml, report
