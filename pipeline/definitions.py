"""Scientific definitions used everywhere in VYOMTRA. Import from here; never redefine."""
from __future__ import annotations

import numpy as np

EARTH_RADIUS_KM = 6371.0088
KT_PER_MS = 1.943844
IST_OFFSET_H = 5.5

# IMD cyclone categories by 3-minute maximum sustained wind (knots): (code, label, lower bound)
IMD_CYCLONE_CATEGORIES = [
    ("D", "Depression", 17),
    ("DD", "Deep Depression", 28),
    ("CS", "Cyclonic Storm", 34),
    ("SCS", "Severe Cyclonic Storm", 48),
    ("VSCS", "Very Severe Cyclonic Storm", 64),
    ("ESCS", "Extremely Severe Cyclonic Storm", 90),
    ("SuCS", "Super Cyclonic Storm", 120),
]

# IMD 24-hour rainfall categories (mm). Thresholds used for exceedance probabilities.
RAIN_THRESHOLDS_MM = {
    "heavy": 64.5,
    "very_heavy": 115.6,
    "extremely_heavy": 204.5,
}
RAIN_LABELS = {
    "heavy": "Heavy rain (≥ 64.5 mm/24 h)",
    "very_heavy": "Very heavy rain (≥ 115.6 mm/24 h)",
    "extremely_heavy": "Extremely heavy rain (≥ 204.5 mm/24 h)",
}

# IMD plains heatwave: Tmax ≥ 40 °C and departure ≥ 4.5 °C, or Tmax ≥ 45 °C.
HEATWAVE_PLAINS = {"tmax_min_c": 40.0, "departure_c": 4.5, "absolute_c": 45.0}

STRIKE_RADIUS_KM = 120.0
SPREAD_QUANTILE = 0.8


def imd_category(wind_kt: float | None) -> dict | None:
    if wind_kt is None or not np.isfinite(wind_kt) or wind_kt < 17:
        return None
    code, label = None, None
    for c, l, lo in IMD_CYCLONE_CATEGORIES:
        if wind_kt >= lo:
            code, label = c, l
    return {"code": code, "label": label}


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def spherical_mean(lats, lons) -> tuple[float, float]:
    """Mean position on the sphere (centroid of unit vectors)."""
    la, lo = np.radians(np.asarray(lats, float)), np.radians(np.asarray(lons, float))
    x, y, z = np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)
    x, y, z = x.mean(), y.mean(), z.mean()
    return float(np.degrees(np.arctan2(z, np.hypot(x, y)))), float(np.degrees(np.arctan2(y, x)))


def destination(lat, lon, bearing_deg, dist_km):
    la, lo, b = np.radians(lat), np.radians(lon), np.radians(bearing_deg)
    d = dist_km / EARTH_RADIUS_KM
    la2 = np.arcsin(np.sin(la) * np.cos(d) + np.cos(la) * np.sin(d) * np.cos(b))
    lo2 = lo + np.arctan2(np.sin(b) * np.sin(d) * np.cos(la), np.cos(d) - np.sin(la) * np.sin(la2))
    return np.degrees(la2), np.degrees(lo2)


def efi(ens_values, clim_quantiles, levels=None) -> float:
    """Extreme Forecast Index (Lalaurette 2003): (2/pi) * integral of (p - F_f(p)) / sqrt(p(1-p)) dp.

    clim_quantiles are the climate's values at probability levels `levels` (default 1..99 %).
    F_f(p) is the fraction of members below the climate's p-quantile. Range -1..+1.
    Not a probability.
    """
    ens = np.sort(np.asarray(ens_values, float))
    levels = np.linspace(0.01, 0.99, len(clim_quantiles)) if levels is None else np.asarray(levels, float)
    q = np.asarray(clim_quantiles, float)
    ff = np.searchsorted(ens, q, side="left") / len(ens)
    integrand = (levels - ff) / np.sqrt(levels * (1 - levels))
    # integrate on the p grid with the trapezoid rule, extended to [0, 1] by the end values
    p = np.concatenate([[0.0], levels, [1.0]])
    f = np.concatenate([[integrand[0]], integrand, [integrand[-1]]])
    return float(np.clip(2 / np.pi * np.trapezoid(f, p), -1, 1))


def sot(ens_values, clim_q90: float, clim_q99: float) -> float | None:
    """Shift of Tails: -(Q_f(90) - Q_c(99)) / (Q_c(90) - Q_c(99)) per ECMWF's definition,
    sign arranged so positive means the ensemble's 90th percentile exceeds the climate 99th."""
    if clim_q99 == clim_q90:
        return None
    qf90 = float(np.percentile(ens_values, 90))
    return float((qf90 - clim_q99) / (clim_q99 - clim_q90))


def utc_to_ist_iso(ts) -> str:
    import pandas as pd

    return (pd.Timestamp(ts) + pd.Timedelta(hours=IST_OFFSET_H)).strftime("%Y-%m-%dT%H:%M") + "+05:30"
