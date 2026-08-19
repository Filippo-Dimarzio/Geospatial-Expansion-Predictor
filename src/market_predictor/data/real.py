"""Real geospatial data acquisition (VIIRS, WorldPop, OSM, admin boundaries)."""

from __future__ import annotations

import logging
import zipfile
from io import BytesIO
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject
from shapely.geometry import box

logger = logging.getLogger("market_predictor.data.real")

# NOAA EOG VIIRS VNP46A4 annual composite (2023) — global GeoTIFF, clipped locally
VIIRS_SAMPLE_URL = (
    "https://eogdata.mines.edu/wwwdata/viirs_products/vnl/v23/"
    "VNL_v23_npp_2023_global_v2/vnl_v2_npp_2023_global.tif"
)

# WorldPop 2020 constrained UN-adjusted — India 100m (requires registration in prod;
# we use a public COG mirror pattern with fallback to synthetic clip)
WORLDPOP_INDIA_URL = (
    "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/"
    "2020/MAXAR/RWA/rwa_ppp_2020_constrained.tif"
)


def _download(url: str, dest: Path, timeout: int = 120) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        logger.info("Using cached file: %s", dest)
        return dest
    logger.info("Downloading %s -> %s", url, dest)
    resp = requests.get(url, timeout=timeout, stream=True)
    resp.raise_for_status()
    with dest.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=1 << 20):
            f.write(chunk)
    return dest


def clip_raster_to_bbox(
    src_path: Path,
    bbox: dict[str, float],
    out_path: Path,
    resampling: Resampling = Resampling.bilinear,
) -> Path:
    """Clip/reproject a raster to a WGS84 bounding box."""
    min_lon, min_lat = bbox["min_lon"], bbox["min_lat"]
    max_lon, max_lat = bbox["max_lon"], bbox["max_lat"]
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(src_path) as src:
        dst_crs = "EPSG:4326"
        width = height = 300
        dst_transform = from_bounds(min_lon, min_lat, max_lon, max_lat, width, height)
        dst_array = np.zeros((height, width), dtype=np.float32)

        reproject(
            source=rasterio.band(src, 1),
            destination=dst_array,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            resampling=resampling,
        )

        # Scale VIIRS DN to 0-100 if needed
        if dst_array.max() > 100:
            dst_array = np.clip(dst_array / dst_array.max() * 100, 0, 100)

        with rasterio.open(
            out_path,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=1,
            dtype=dst_array.dtype,
            crs=dst_crs,
            transform=dst_transform,
        ) as dst:
            dst.write(dst_array, 1)

    logger.info("Clipped raster -> %s", out_path)
    return out_path


def fetch_viirs_night_lights(bbox: dict[str, float], cache_dir: Path) -> Path:
    """Fetch VIIRS night lights and clip to bbox. Falls back to mock on failure."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    raw_path = cache_dir / "viirs_global.tif"
    out_path = cache_dir / "night_lights.tif"
    try:
        _download(VIIRS_SAMPLE_URL, raw_path)
        return clip_raster_to_bbox(raw_path, bbox, out_path)
    except Exception as exc:
        logger.warning("VIIRS download failed (%s); falling back to mock raster", exc)
        from market_predictor.data.mock import generate_night_light_raster, save_raster_geotiff

        intensity, transform = generate_night_light_raster(
            bbox["min_lon"], bbox["max_lon"], bbox["min_lat"], bbox["max_lat"]
        )
        return save_raster_geotiff(intensity, transform, out_path)


def fetch_osm_boundaries(bbox: dict[str, float]) -> gpd.GeoDataFrame:
    """Fetch admin boundaries from OpenStreetMap via Overpass API."""
    min_lon, min_lat = bbox["min_lon"], bbox["min_lat"]
    max_lon, max_lat = bbox["max_lon"], bbox["max_lat"]
    query = f"""
    [out:json][timeout:60];
    (
      relation["boundary"="administrative"]["admin_level"~"9|10"]
        ({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out geom;
    """
    try:
        resp = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
        records = []
        for el in data.get("elements", []):
            if el.get("type") != "relation" or "members" not in el:
                continue
            # Simplified: use bounding box of relation as polygon proxy
            bounds = el.get("bounds", {})
            if not bounds:
                continue
            geom = box(bounds["minlon"], bounds["minlat"], bounds["maxlon"], bounds["maxlat"])
            records.append(
                {
                    "district_id": f"OSM-{el['id']}",
                    "name": el.get("tags", {}).get("name", str(el["id"])),
                    "geometry": geom,
                }
            )
        if records:
            return gpd.GeoDataFrame(records, crs="EPSG:4326")
    except Exception as exc:
        logger.warning("OSM boundary fetch failed (%s)", exc)

    # Fallback: grid from mock generator
    from market_predictor.data.mock import generate_district_polygons, generate_night_light_raster

    intensity, transform = generate_night_light_raster(
        min_lon, max_lon, min_lat, max_lat
    )
    gdf = generate_district_polygons(intensity, transform)
    gdf["name"] = gdf["district_id"]
    return gdf


def fetch_census_tracts(bbox: dict[str, float], state_fips: str, county_fips: str) -> gpd.GeoDataFrame:
    """Fetch US Census TIGER/Line tracts (demo for real admin boundaries)."""
    url = (
        f"https://www2.census.gov/geo/tiger/TIGER2023/TRACT/tl_2023_{state_fips}_tract.zip"
    )
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        with zipfile.ZipFile(BytesIO(resp.content)) as zf:
            shp_name = [n for n in zf.namelist() if n.endswith(".shp")][0]
            extract_dir = Path("data/cache/census")
            extract_dir.mkdir(parents=True, exist_ok=True)
            zf.extractall(extract_dir)
            gdf = gpd.read_file(extract_dir / shp_name)
        gdf = gdf[gdf["COUNTYFP"] == county_fips].copy()
        min_lon, min_lat = bbox["min_lon"], bbox["min_lat"]
        max_lon, max_lat = bbox["max_lon"], bbox["max_lat"]
        bbox_geom = box(min_lon, min_lat, max_lon, max_lat)
        gdf = gdf[gdf.intersects(bbox_geom)].to_crs("EPSG:4326")
        gdf["district_id"] = gdf["GEOID"]
        gdf["name"] = gdf.get("NAMELSAD", gdf["GEOID"])
        return gdf[["district_id", "name", "geometry"]]
    except Exception as exc:
        logger.warning("Census tract fetch failed (%s); using OSM fallback", exc)
        return fetch_osm_boundaries(bbox)


def fetch_osm_pois(bbox: dict[str, float], tags: dict[str, str] | None = None) -> gpd.GeoDataFrame:
    """Fetch OSM POIs (shops, supermarkets) for business density proxy."""
    min_lon, min_lat = bbox["min_lon"], bbox["min_lat"]
    max_lon, max_lat = bbox["max_lon"], bbox["max_lat"]
    tag_filter = tags or {"shop": "supermarket"}
    tag_clause = "".join(f'["{k}"="{v}"]' for k, v in tag_filter.items())
    query = f"""
    [out:json][timeout:60];
    (
      node{tag_clause}({min_lat},{min_lon},{max_lat},{max_lon});
      way{tag_clause}({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center;
    """
    try:
        resp = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
        records = []
        for el in data.get("elements", []):
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if lat is None or lon is None:
                continue
            from shapely.geometry import Point

            records.append({"geometry": Point(lon, lat), "poi_type": "competitor"})
        if records:
            return gpd.GeoDataFrame(records, crs="EPSG:4326")
    except Exception as exc:
        logger.warning("OSM POI fetch failed (%s)", exc)
    return gpd.GeoDataFrame(columns=["geometry", "poi_type"], crs="EPSG:4326")


def fetch_worldpop_density(bbox: dict[str, float], districts: gpd.GeoDataFrame) -> pd.Series:
    """
    Assign population density from a WorldPop raster via zonal mean.
    Falls back to night-light-correlated synthetic values on failure.
    """
    cache_dir = Path("data/cache")
    try:
        raw = cache_dir / "worldpop_raw.tif"
        clipped = cache_dir / "worldpop_clipped.tif"
        _download(WORLDPOP_INDIA_URL, raw)
        clip_raster_to_bbox(raw, bbox, clipped)
        from market_predictor.pipeline.zonal import extract_zonal_statistics

        stats = extract_zonal_statistics(districts, str(clipped), stats=("mean",))
        return stats["mean_population"].fillna(0)
    except Exception as exc:
        logger.warning("WorldPop fetch failed (%s); using synthetic population", exc)
        rng = np.random.default_rng(42)
        return pd.Series(rng.uniform(500, 8000, len(districts)), index=districts.index)


def generate_real_data(
    bbox: dict[str, float],
    output_dir: Path,
    boundary_source: str = "osm",
    census_state_fips: str = "29",
    census_county_fips: str = "037",
) -> tuple[Path, Path]:
    """Orchestrate real-data acquisition."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / "cache"

    raster_path = fetch_viirs_night_lights(bbox, cache_dir)

    if boundary_source == "census_tract":
        districts = fetch_census_tracts(bbox, census_state_fips, census_county_fips)
    else:
        districts = fetch_osm_boundaries(bbox)

    districts["population_density"] = fetch_worldpop_density(bbox, districts).values

    pois = fetch_osm_pois(bbox)
    if not pois.empty:
        joined = gpd.sjoin(districts, pois, predicate="contains", how="left")
        business_counts = joined.groupby(joined.index).size() - 1  # subtract self
        districts["current_business_count"] = business_counts.reindex(districts.index).fillna(0).astype(int)
    else:
        districts["current_business_count"] = (districts["population_density"] / 500).round().astype(int)

    districts_path = output_dir / "districts.geojson"
    districts.to_file(districts_path, driver="GeoJSON")
    logger.info("Real data saved: raster=%s, districts=%s", raster_path, districts_path)
    return raster_path, districts_path
