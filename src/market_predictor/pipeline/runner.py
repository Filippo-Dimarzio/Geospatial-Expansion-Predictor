"""Pipeline orchestration, persistence, and batch raster processing."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import geopandas as gpd

from market_predictor.config import AppConfig
from market_predictor.data.features import add_synthetic_features
from market_predictor.pipeline.opportunity import identify_high_potential_zones
from market_predictor.pipeline.scoring import calculate_market_potential_score
from market_predictor.pipeline.sensitivity import rank_stability_summary, run_sensitivity_analysis
from market_predictor.pipeline.spatial import add_spatial_features
from market_predictor.pipeline.zonal import (
    extract_zonal_statistics,
    extract_zonal_statistics_batched,
)

logger = logging.getLogger("market_predictor.pipeline.runner")


def persist_outputs(gdf: gpd.GeoDataFrame, geojson_path: str, parquet_path: str) -> None:
    """Save pipeline results to GeoJSON and Parquet."""
    geojson = Path(geojson_path)
    parquet = Path(parquet_path)
    geojson.parent.mkdir(parents=True, exist_ok=True)
    parquet.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(geojson, driver="GeoJSON")
    # Parquet without geometry for analytics; also save geometry version
    gdf.drop(columns="geometry").to_parquet(parquet, index=False)
    logger.info("Persisted results -> %s, %s", geojson, parquet)


def load_precomputed(path: str) -> gpd.GeoDataFrame | None:
    p = Path(path)
    if p.exists():
        logger.info("Loading precomputed results from %s", p)
        return gpd.read_file(p)
    return None


def run_pipeline(
    districts_path: str | None = None,
    raster_path: str | None = None,
    config: AppConfig | None = None,
    light_weight: float | None = None,
    population_weight: float | None = None,
    skip_zonal: bool = False,
    precomputed_path: str | None = None,
) -> gpd.GeoDataFrame:
    cfg = config or AppConfig.load()
    districts_path = districts_path or cfg.districts_path
    raster_path = raster_path or cfg.raster_path

    precomputed = precomputed_path or cfg.output_path
    if skip_zonal:
        loaded = load_precomputed(precomputed)
        if loaded is not None:
            gdf = loaded
        else:
            raise FileNotFoundError(f"No precomputed results at {precomputed}")

    else:
        districts = gpd.read_file(districts_path)
        zonal_backend = cfg.get("pipeline", "zonal_backend", default="auto")
        batch_size = cfg.get("pipeline", "batch_size", default=50)
        use_mp = cfg.get("pipeline", "use_multiprocessing", default=False)
        n_workers = cfg.get("pipeline", "n_workers", default=4)

        if cfg.get("pipeline", "use_multiprocessing", default=False):
            gdf = extract_zonal_statistics_batched(
                districts,
                raster_path,
                batch_size=batch_size,
                backend=zonal_backend,
                use_multiprocessing=use_mp,
                n_workers=n_workers,
            )
        else:
            gdf = extract_zonal_statistics(districts, raster_path, backend=zonal_backend)

        gdf = add_synthetic_features(gdf)

    lw = light_weight if light_weight is not None else cfg.get("scoring", "light_weight", default=0.6)
    pw = (
        population_weight
        if population_weight is not None
        else cfg.get("scoring", "population_weight", default=0.4)
    )
    method = cfg.get("scoring", "method", default="weighted")
    feature_weights = cfg.get("scoring", "feature_weights", default={})
    normalize = cfg.get("scoring", "normalize_weights", default=True)
    spatial_lag_w = cfg.get("scoring", "spatial_lag_weight", default=0.0)

    scored = calculate_market_potential_score(
        gdf,
        light_weight=lw,
        population_weight=pw,
        normalize_weight_sum=normalize,
        method=method,
        feature_weights=feature_weights,
        spatial_lag_weight=spatial_lag_w,
    )

    compute_morans = cfg.get("scoring", "compute_morans_i", default=True)
    scored, morans_i = add_spatial_features(scored, compute_morans=compute_morans)
    if morans_i is not None:
        scored.attrs["morans_i"] = morans_i

    result = identify_high_potential_zones(
        scored,
        business_density_percentile=cfg.get("opportunity", "business_density_percentile", default=40),
        market_potential_percentile=cfg.get("opportunity", "market_potential_percentile", default=70),
        business_column=cfg.get("opportunity", "business_column", default="current_business_count"),
        score_column=cfg.get("opportunity", "score_column", default="market_potential_score"),
    )

    if cfg.get("pipeline", "persist_outputs", default=True) and not skip_zonal:
        persist_outputs(result, cfg.output_path, cfg.parquet_path)

    return result


def run_sensitivity(cfg: AppConfig | None = None) -> tuple[Any, Any]:
    cfg = cfg or AppConfig.load()
    gdf = run_pipeline(config=cfg, skip_zonal=False)
    sens_cfg = cfg.get("sensitivity", default={})
    sens_df = run_sensitivity_analysis(
        gdf.drop(columns=["is_high_potential_untapped", "opportunity_rank"], errors="ignore"),
        light_weight_range=tuple(sens_cfg.get("light_weight_range", [0.2, 0.8])),
        n_steps=sens_cfg.get("n_steps", 7),
        business_density_percentile=cfg.get("opportunity", "business_density_percentile", default=40),
        market_potential_percentile=cfg.get("opportunity", "market_potential_percentile", default=70),
    )
    summary = rank_stability_summary(sens_df)
    return sens_df, summary
