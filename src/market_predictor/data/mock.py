"""Synthetic geospatial data generator."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from shapely.geometry import box

logger = logging.getLogger("market_predictor.data.mock")

RNG = np.random.default_rng(7)

# Default focus: Europe, with US as optional alternate region.
DEFAULT_BBOX = {
    "min_lon": -10.0,
    "max_lon": 30.0,
    "min_lat": 35.0,
    "max_lat": 72.0,
}
US_BBOX = {
    "min_lon": -125.0,
    "max_lon": -66.0,
    "min_lat": 24.0,
    "max_lat": 50.0,
}
RASTER_WIDTH = 300
RASTER_HEIGHT = 300
DISTRICT_GRID_COLS = 12
DISTRICT_GRID_ROWS = 12

MIN_LON, MAX_LON = DEFAULT_BBOX["min_lon"], DEFAULT_BBOX["max_lon"]
MIN_LAT, MAX_LAT = DEFAULT_BBOX["min_lat"], DEFAULT_BBOX["max_lat"]


def _gaussian_blob(xx, yy, cx, cy, sigma, amplitude):
    return amplitude * np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma**2)))


def _region_urban_centers(region: str) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
    region_key = (region or "europe").lower()
    if region_key == "united_states":
        urban_cores = [
            {"lon": -122.4194, "lat": 37.7749, "sigma": 2.1, "amplitude": 110},
            {"lon": -118.2437, "lat": 34.0522, "sigma": 2.0, "amplitude": 98},
            {"lon": -87.6298, "lat": 41.8781, "sigma": 2.2, "amplitude": 105},
            {"lon": -74.0060, "lat": 40.7128, "sigma": 2.0, "amplitude": 104},
            {"lon": -96.7970, "lat": 32.7767, "sigma": 2.1, "amplitude": 92},
            {"lon": -80.1918, "lat": 25.7617, "sigma": 1.8, "amplitude": 90},
        ]
        suburbs = [
            {"lon": -122.3321, "lat": 47.6062, "sigma": 2.8, "amplitude": 54},
            {"lon": -118.2437, "lat": 33.9, "sigma": 2.6, "amplitude": 48},
            {"lon": -88.0, "lat": 42.1, "sigma": 2.5, "amplitude": 51},
            {"lon": -73.9, "lat": 40.7, "sigma": 2.5, "amplitude": 49},
            {"lon": -95.9, "lat": 29.7604, "sigma": 2.8, "amplitude": 46},
            {"lon": -81.4, "lat": 28.5393, "sigma": 2.6, "amplitude": 42},
        ]
        return urban_cores, suburbs

    urban_cores = [
        {"lon": 2.3522, "lat": 48.8566, "sigma": 1.4, "amplitude": 108},
        {"lon": 13.4050, "lat": 52.5200, "sigma": 1.6, "amplitude": 102},
        {"lon": -0.1278, "lat": 51.5074, "sigma": 1.5, "amplitude": 100},
        {"lon": 2.1734, "lat": 41.3851, "sigma": 1.7, "amplitude": 96},
        {"lon": 9.1900, "lat": 45.4642, "sigma": 1.5, "amplitude": 92},
        {"lon": 23.7275, "lat": 37.9838, "sigma": 1.4, "amplitude": 88},
    ]
    suburbs = [
        {"lon": 2.2, "lat": 49.1, "sigma": 2.6, "amplitude": 52},
        {"lon": 13.0, "lat": 53.0, "sigma": 2.7, "amplitude": 49},
        {"lon": -0.1, "lat": 51.4, "sigma": 2.5, "amplitude": 47},
        {"lon": 2.0, "lat": 41.0, "sigma": 2.4, "amplitude": 45},
        {"lon": 8.7, "lat": 45.9, "sigma": 2.5, "amplitude": 43},
        {"lon": 23.0, "lat": 38.2, "sigma": 2.6, "amplitude": 41},
    ]
    return urban_cores, suburbs


def generate_night_light_raster(
    min_lon: float | None = None,
    max_lon: float | None = None,
    min_lat: float | None = None,
    max_lat: float | None = None,
    width: int = RASTER_WIDTH,
    height: int = RASTER_HEIGHT,
    region: str = "europe",
) -> tuple[np.ndarray, object]:
    min_lon = DEFAULT_BBOX["min_lon"] if min_lon is None else min_lon
    max_lon = DEFAULT_BBOX["max_lon"] if max_lon is None else max_lon
    min_lat = DEFAULT_BBOX["min_lat"] if min_lat is None else min_lat
    max_lat = DEFAULT_BBOX["max_lat"] if max_lat is None else max_lat
    x = np.linspace(min_lon, max_lon, width)
    y = np.linspace(max_lat, min_lat, height)
    xx, yy = np.meshgrid(x, y)
    intensity = np.zeros((height, width), dtype=np.float64)
    intensity += RNG.normal(loc=2.5, scale=1.2, size=intensity.shape).clip(0, None)

    urban_cores, suburbs = _region_urban_centers(region)
    for core in urban_cores:
        intensity += _gaussian_blob(xx, yy, core["lon"], core["lat"], core["sigma"], core["amplitude"])
    for sub in suburbs:
        intensity += _gaussian_blob(xx, yy, sub["lon"], sub["lat"], sub["sigma"], sub["amplitude"])

    intensity += RNG.normal(loc=0, scale=2.0, size=intensity.shape)
    intensity = np.clip(intensity, 0, 150)
    transform = from_bounds(min_lon, min_lat, max_lon, max_lat, width, height)
    return intensity, transform


def save_raster_geotiff(intensity: np.ndarray, transform, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        out_path,
        "w",
        driver="GTiff",
        height=intensity.shape[0],
        width=intensity.shape[1],
        count=1,
        dtype=intensity.dtype,
        crs="EPSG:4326",
        transform=transform,
        nodata=None,
    ) as dst:
        dst.write(intensity, 1)
    logger.info("Saved raster -> %s", out_path)
    return out_path


def generate_district_polygons(intensity: np.ndarray, transform, bbox: dict[str, float] | None = None) -> gpd.GeoDataFrame:
    bbox = bbox or DEFAULT_BBOX
    min_lon = bbox["min_lon"]
    max_lon = bbox["max_lon"]
    min_lat = bbox["min_lat"]
    max_lat = bbox["max_lat"]
    lon_edges = np.linspace(min_lon, max_lon, DISTRICT_GRID_COLS + 1)
    lat_edges = np.linspace(min_lat, max_lat, DISTRICT_GRID_ROWS + 1)
    records = []
    district_id = 0
    for i in range(DISTRICT_GRID_ROWS):
        for j in range(DISTRICT_GRID_COLS):
            minx, maxx = lon_edges[j], lon_edges[j + 1]
            miny, maxy = lat_edges[i], lat_edges[i + 1]
            centroid_lon = (minx + maxx) / 2
            centroid_lat = (miny + maxy) / 2
            col = int((centroid_lon - min_lon) / (max_lon - min_lon) * (intensity.shape[1] - 1))
            row = int((max_lat - centroid_lat) / (max_lat - min_lat) * (intensity.shape[0] - 1))
            approx_light = intensity[row, col]
            pop_density = max(50, approx_light * RNG.uniform(35, 55) + RNG.normal(0, 400))
            records.append(
                {
                    "district_id": f"D-{district_id:03d}",
                    "geometry": box(minx, miny, maxx, maxy),
                    "population_density": round(pop_density, 1),
                }
            )
            district_id += 1

    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    base_business_count = (
        gdf["population_density"] / 40 * RNG.uniform(0.6, 1.4, len(gdf))
    ).round().astype(int)
    high_density_idx = gdf["population_density"].sort_values(ascending=False).index[:6]
    underserved_idx = RNG.choice(high_density_idx, size=3, replace=False)
    base_business_count.loc[underserved_idx] = RNG.integers(1, 5, size=3)
    gdf["current_business_count"] = base_business_count.clip(lower=0)
    return gdf


def generate_mock_data(
    raster_path: str | Path = "data/night_lights.tif",
    districts_path: str | Path = "data/districts.geojson",
    bbox: dict[str, float] | None = None,
    region: str = "europe",
) -> tuple[Path, Path]:
    """Generate synthetic raster + district polygons for a default region."""
    bbox = bbox or (US_BBOX if region.lower() == "united_states" else DEFAULT_BBOX)
    intensity, transform = generate_night_light_raster(
        bbox["min_lon"], bbox["max_lon"], bbox["min_lat"], bbox["max_lat"], region=region
    )
    raster_out = save_raster_geotiff(intensity, transform, raster_path)
    districts_gdf = generate_district_polygons(intensity, transform, bbox=bbox)
    districts_path = Path(districts_path)
    districts_path.parent.mkdir(parents=True, exist_ok=True)
    districts_gdf.to_file(districts_path, driver="GeoJSON")
    logger.info("Saved %d %s districts -> %s", len(districts_gdf), region, districts_path)
    return raster_out, districts_path
