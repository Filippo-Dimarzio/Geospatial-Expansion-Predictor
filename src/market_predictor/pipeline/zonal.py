"""Zonal statistics with rasterstats / exactextract / manual fallback."""

from __future__ import annotations

import logging
from typing import Literal, Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask

logger = logging.getLogger("market_predictor.pipeline.zonal")

StatName = Literal["mean", "max", "count"]
Backend = Literal["auto", "rasterstats", "exactextract", "manual"]


def _resolve_backend(backend: Backend) -> str:
    if backend != "auto":
        return backend
    try:
        import rasterstats  # noqa: F401

        return "rasterstats"
    except ImportError:
        pass
    try:
        import exactextract  # noqa: F401

        return "exactextract"
    except ImportError:
        pass
    return "manual"


def _zonal_rasterstats(
    gdf: gpd.GeoDataFrame,
    raster_path: str,
    stats: Sequence[StatName],
) -> gpd.GeoDataFrame:
    from rasterstats import zonal_stats

    out = gdf.copy()
    with rasterio.open(raster_path) as src:
        if out.crs != src.crs:
            out = out.to_crs(src.crs)
        geojson_feats = [feat.__geo_interface__ for feat in out.geometry]
        results = zonal_stats(geojson_feats, raster_path, stats=list(stats), nodata=src.nodata)

    for stat in stats:
        col = f"{stat}_night_light" if stat != "count" else "pixel_count"
        if stat == "mean":
            col = "mean_night_light"
        elif stat == "max":
            col = "peak_night_light"
        out[col] = [r.get(stat) for r in results]
    return out


def _zonal_exactextract(gdf: gpd.GeoDataFrame, raster_path: str) -> gpd.GeoDataFrame:
    import exactextract

    out = gdf.copy()
    with rasterio.open(raster_path) as src:
        if out.crs != src.crs:
            out = out.to_crs(src.crs)
        mean_vals = exactextract.exact_extract(raster_path, out, "mean")
        max_vals = exactextract.exact_extract(raster_path, out, "max")
        count_vals = exactextract.exact_extract(raster_path, out, "count")
    out["mean_night_light"] = np.round(mean_vals, 2)
    out["peak_night_light"] = np.round(max_vals, 2)
    out["pixel_count"] = count_vals.astype(int)
    return out


def _zonal_manual(gdf: gpd.GeoDataFrame, raster_path: str) -> gpd.GeoDataFrame:
    out = gdf.copy()
    with rasterio.open(raster_path) as src:
        band = src.read(1)
        transform = src.transform
        raster_crs = src.crs
        if out.crs != raster_crs:
            out = out.to_crs(raster_crs)

        means, peaks, pixel_counts = [], [], []
        for geom in out.geometry:
            mask = geometry_mask(
                [geom.__geo_interface__],
                out_shape=band.shape,
                transform=transform,
                invert=True,
            )
            pixels = band[mask]
            if pixels.size == 0:
                row, col = src.index(geom.centroid.x, geom.centroid.y)
                row = np.clip(row, 0, band.shape[0] - 1)
                col = np.clip(col, 0, band.shape[1] - 1)
                pixels = np.array([band[row, col]])
            means.append(float(np.mean(pixels)))
            peaks.append(float(np.max(pixels)))
            pixel_counts.append(int(pixels.size))

    out["mean_night_light"] = np.round(means, 2)
    out["peak_night_light"] = np.round(peaks, 2)
    out["pixel_count"] = pixel_counts
    return out


def extract_zonal_statistics(
    districts_gdf: gpd.GeoDataFrame,
    raster_path: str,
    backend: Backend = "auto",
    stats: Sequence[StatName] = ("mean", "max", "count"),
) -> gpd.GeoDataFrame:
    """
    Compute per-polygon raster statistics using the best available backend.
    Column naming is consistent across backends for downstream compatibility.
    """
    resolved = _resolve_backend(backend)
    logger.info("Zonal statistics backend: %s", resolved)

    if resolved == "rasterstats":
        return _zonal_rasterstats(districts_gdf, raster_path, stats)
    if resolved == "exactextract":
        return _zonal_exactextract(districts_gdf, raster_path)
    return _zonal_manual(districts_gdf, raster_path)


def extract_zonal_statistics_batched(
    districts_gdf: gpd.GeoDataFrame,
    raster_path: str,
    batch_size: int = 50,
    backend: Backend = "auto",
    use_multiprocessing: bool = False,
    n_workers: int = 4,
) -> gpd.GeoDataFrame:
    """Process districts in batches; optional multiprocessing for manual backend."""
    if _resolve_backend(backend) != "manual" or not use_multiprocessing:
        # rasterstats/exactextract are already vectorized
        return extract_zonal_statistics(districts_gdf, raster_path, backend=backend)

    from concurrent.futures import ProcessPoolExecutor

    indices = list(range(0, len(districts_gdf), batch_size))
    chunks = [districts_gdf.iloc[i : i + batch_size] for i in indices]
    results = []
    with ProcessPoolExecutor(max_workers=n_workers) as pool:
        futures = [
            pool.submit(extract_zonal_statistics, chunk, raster_path, "manual") for chunk in chunks
        ]
        for fut in futures:
            results.append(fut.result())
    return gpd.GeoDataFrame(pd.concat(results, ignore_index=True), crs=districts_gdf.crs)


def rename_population_columns(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out = gdf.copy()
    if "mean_night_light" not in out.columns and "mean" in out.columns:
        out["mean_night_light"] = out["mean"]
    if "mean_population" in out.columns and "population_density" not in out.columns:
        out["population_density"] = out["mean_population"]
    return out
