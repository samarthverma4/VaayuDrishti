"""Boundaries for the map and for district aggregation.

Sources (licences recorded in data/sources.yaml):
- Countries: Natural Earth 1:10m admin-0, India point of view (public domain), so India's
  boundaries follow the official depiction.
- States and districts: geoBoundaries gbOpen IND ADM1 (CC BY 2.5 IN) and ADM2 (ODbL 1.0,
  from lgdirectory.gov.in).
- Land and coastline: Natural Earth 1:10m physical (public domain).
"""
from __future__ import annotations

import json
import unicodedata
from functools import lru_cache

import geopandas as gpd
import shapely
from shapely.geometry import box

from pipeline.config import ARTIFACTS, RAW

GEO_RAW = RAW / "geo"
GEO_OUT = ARTIFACTS / "geo"
MAP_BBOX = (45.0, -5.0, 105.0, 40.0)  # lon_min, lat_min, lon_max, lat_max


DOWNLOADS = {
    "ne_10m_admin_0_countries_ind.zip": "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries_ind.zip",
    "ne_10m_land.zip": "https://naciscdn.org/naturalearth/10m/physical/ne_10m_land.zip",
    "ne_10m_coastline.zip": "https://naciscdn.org/naturalearth/10m/physical/ne_10m_coastline.zip",
    "IND-ADM1.geojson": "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND/ADM1/geoBoundaries-IND-ADM1_simplified.geojson",
    "IND-ADM2.geojson": "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND/ADM2/geoBoundaries-IND-ADM2_simplified.geojson",
    "CAP-v1.2.xsd": "https://docs.oasis-open.org/emergency/cap/v1.2/CAP-v1.2.xsd",
}


def download() -> None:
    import requests

    GEO_RAW.mkdir(parents=True, exist_ok=True)
    for name, url in DOWNLOADS.items():
        path = GEO_RAW / name
        if path.exists():
            continue
        r = requests.get(url, timeout=300)
        r.raise_for_status()
        path.write_bytes(r.content)


def ascii_name(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in ascii_name(s).lower()).strip("-")


@lru_cache
def districts() -> gpd.GeoDataFrame:
    d = gpd.read_file(GEO_RAW / "IND-ADM2.geojson")[["shapeName", "shapeID", "geometry"]]
    s = gpd.read_file(GEO_RAW / "IND-ADM1.geojson")[["shapeName", "geometry"]].rename(columns={"shapeName": "state"})
    d = d.to_crs(4326)
    d["geometry"] = d.geometry.make_valid()
    s["geometry"] = s.geometry.make_valid()
    # assign each district to the state it overlaps most
    pts = d.copy()
    pts["geometry"] = d.geometry.representative_point()
    j = gpd.sjoin(pts, s, how="left", predicate="within")
    j = j[~j.index.duplicated()]
    d["state"] = j["state"].fillna("")
    missing = d["state"] == ""
    if missing.any():
        nearest = gpd.sjoin_nearest(d.loc[missing, ["geometry"]].to_crs(3857), s.to_crs(3857), how="left")
        d.loc[missing, "state"] = nearest.groupby(level=0)["state"].first()
    d["name"] = d["shapeName"].map(ascii_name)
    d["state"] = d["state"].map(ascii_name)
    d["id"] = [f"{_slug(st)}--{_slug(n)}" for st, n in zip(d.state, d.name)]
    dup = d["id"].duplicated(keep=False)
    d.loc[dup, "id"] = d.loc[dup, "id"] + "--" + d.loc[dup, "shapeID"].str[-6:]
    return d[["id", "name", "state", "geometry"]].reset_index(drop=True)


@lru_cache
def land() -> shapely.Geometry:
    g = gpd.read_file(GEO_RAW / "ne_10m_land.zip").clip(box(*MAP_BBOX))
    return shapely.union_all(g.geometry.values)


def is_land(lat, lon) -> "np.ndarray":
    import numpy as np

    geom = land()
    shapely.prepare(geom)
    return shapely.contains_xy(geom, np.asarray(lon), np.asarray(lat))


def build() -> None:
    """Write simplified GeoJSON layers for the frontend basemap and district lookup."""
    GEO_OUT.mkdir(parents=True, exist_ok=True)
    clip = box(*MAP_BBOX)
    countries = gpd.read_file(GEO_RAW / "ne_10m_admin_0_countries_ind.zip")[["NAME_EN", "ADM0_A3", "geometry"]]
    countries = countries.clip(clip)
    countries["geometry"] = countries.geometry.simplify(0.02, preserve_topology=True)
    countries = countries.rename(columns={"NAME_EN": "name", "ADM0_A3": "iso3"})
    countries["name"] = countries["name"].map(ascii_name)
    countries.to_file(GEO_OUT / "countries.geojson", driver="GeoJSON")

    states = gpd.read_file(GEO_RAW / "IND-ADM1.geojson")[["shapeName", "geometry"]]
    states["name"] = states["shapeName"].map(ascii_name)
    states["geometry"] = states.geometry.simplify(0.01, preserve_topology=True)
    states[["name", "geometry"]].to_file(GEO_OUT / "states.geojson", driver="GeoJSON")

    d = districts().copy()
    d["geometry"] = d.geometry.simplify(0.008, preserve_topology=True)
    d = d.set_crs(4326, allow_override=True)
    d.to_file(GEO_OUT / "districts.geojson", driver="GeoJSON", COORDINATE_PRECISION=4)
    index = [
        {"id": r.id, "name": r.name, "state": r.state,
         "bbox": [round(v, 3) for v in r.geometry.bounds],
         "centroid": [round(r.geometry.representative_point().x, 3), round(r.geometry.representative_point().y, 3)]}
        for r in d.itertuples()
    ]
    (GEO_OUT / "districts_index.json").write_text(json.dumps(index))

    coast = gpd.read_file(GEO_RAW / "ne_10m_coastline.zip").clip(clip)
    coast["geometry"] = coast.geometry.simplify(0.01)
    coast[["geometry"]].to_file(GEO_OUT / "coastline.geojson", driver="GeoJSON")


if __name__ == "__main__":
    download()
    build()
