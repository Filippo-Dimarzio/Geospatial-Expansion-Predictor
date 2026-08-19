"""Enrich districts with income, road access, competitors, delivery radius."""

from __future__ import annotations

import logging

import geopandas as gpd
import numpy as np
import pandas as pd

logger = logging.getLogger("market_predictor.data.features")

RNG = np.random.default_rng(11)


def add_synthetic_features(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Add extended features for MCDA scoring.
    In production, replace with census income, OSM road network, competitor DB.
    """
    out = gdf.copy()
    light = out.get("mean_night_light", pd.Series(RNG.uniform(5, 80, len(out)), index=out.index))
    pop = out.get("population_density", pd.Series(RNG.uniform(500, 10000, len(out)), index=out.index))

    out["median_income"] = (light * 800 + pop * 0.5 + RNG.normal(0, 5000, len(out))).clip(15000, 150000).round(0)
    out["road_access_score"] = (light / 100 * 0.6 + RNG.uniform(0, 0.4, len(out))).clip(0, 1).round(3)
    out["competitor_count"] = out.get(
        "current_business_count", pd.Series(RNG.integers(0, 20, len(out)), index=out.index)
    )
    # Delivery radius: inverse of competitor density + road access bonus
    out["delivery_radius_km"] = (
        5.0 - out["competitor_count"] * 0.15 + out["road_access_score"] * 2
    ).clip(1.5, 8.0).round(2)
    return out


def add_road_network_access(gdf: gpd.GeoDataFrame, bbox: dict[str, float] | None = None) -> gpd.GeoDataFrame:
    """Compute road access from OSM highway network via osmnx (optional)."""
    out = gdf.copy()
    try:
        import osmnx as ox

        if bbox is None:
            bounds = out.total_bounds
            bbox = {"min_lon": bounds[0], "min_lat": bounds[1], "max_lon": bounds[2], "max_lat": bounds[3]}
        G = ox.graph_from_bbox(
            bbox["max_lat"], bbox["min_lat"], bbox["max_lon"], bbox["min_lon"], network_type="drive"
        )
        nodes = ox.graph_to_gdfs(G, nodes=True, edges=False)
        nodes = nodes.to_crs(out.crs)
        scores = []
        for geom in out.geometry:
            centroid = geom.centroid
            dists = nodes.geometry.distance(centroid)
            nearest_dist = dists.min() if len(dists) else 0.01
            scores.append(float(np.clip(1.0 - nearest_dist * 100, 0, 1)))
        out["road_access_score"] = scores
        logger.info("Road access computed via osmnx (%d nodes)", len(nodes))
    except ImportError:
        logger.debug("osmnx not installed; keeping synthetic road_access_score")
    except Exception as exc:
        logger.warning("Road network analysis failed (%s)", exc)
    return out
