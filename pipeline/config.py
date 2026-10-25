"""Paths and fixed settings shared by every pipeline stage."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
CACHE = DATA / "cache"
ARTIFACTS = ROOT / "artifacts"

# Analysis domain for India and the North Indian Ocean (degrees).
DOMAIN = {"lat_min": 0.0, "lat_max": 35.0, "lon_min": 55.0, "lon_max": 100.0}

# Leads kept from each forecast (hours). The archive goes to 360 h; cyclone
# guidance beyond 10 days adds little and costs disk.
MAX_LEAD_H = 240

IBTRACS_NI_URL = (
    "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/"
    "v04r01/access/csv/ibtracs.NI.list.v04r01.csv"
)

DYNAMICAL_ENS = {
    "bucket": "dynamical-ecmwf-ifs-ens",
    "prefix": "ecmwf-ifs-ens-forecast-15-day-0-25-degree/v0.1.0.icechunk",
    "region": "us-west-2",
}

# Variables pulled from the ENS archive, keyed by the short names used in the pipeline.
ENS_VARS = {
    "msl": "pressure_reduced_to_mean_sea_level",  # Pa
    "u10": "wind_u_10m",  # m/s
    "v10": "wind_v_10m",  # m/s
    "prate": "precipitation_surface",  # kg m-2 s-1, mean since previous step
}

for p in (RAW, CACHE, ARTIFACTS):
    p.mkdir(parents=True, exist_ok=True)
