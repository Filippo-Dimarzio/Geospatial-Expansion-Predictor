"""Spatial autocorrelation: Moran's I and spatial lag features."""

from __future__ import annotations

import logging

import geopandas as gpd
import numpy as np
import pandas as pd

logger = logging.getLogger("market_predictor.pipeline.spatial")


def build_queen_weights(gdf: gpd.GeoDataFrame) -> np.ndarray:
    """Build row-standardized queen contiguity weight matrix."""
    n = len(gdf)
    W = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if gdf.geometry.iloc[i].touches(gdf.geometry.iloc[j]):
                W[i, j] = 1
    row_sums = W.sum(axis=1)
    row_sums[row_sums == 0] = 1
    return W / row_sums[:, np.newaxis]


def compute_spatial_lag(gdf: gpd.GeoDataFrame, column: str = "market_potential_score") -> pd.Series:
    """Spatial lag: weighted average of neighbors' values."""
    if column not in gdf.columns:
        column = "mean_night_light"
    W = build_queen_weights(gdf)
    values = gdf[column].astype(float).values
    lag = W @ values
    return pd.Series(lag, index=gdf.index, name="spatial_lag_score")


def compute_morans_i(gdf: gpd.GeoDataFrame, column: str = "market_potential_score") -> float:
    """
    Global Moran's I statistic for spatial autocorrelation.
    Returns I in [-1, 1]; positive = clustering of similar values.
    """
    if column not in gdf.columns:
        return float("nan")
    x = gdf[column].astype(float).values
    n = len(x)
    if n < 3:
        return float("nan")
    W = build_queen_weights(gdf)
    x_dev = x - x.mean()
    num = n * (x_dev @ W @ x_dev)
    den = (W.sum()) * (x_dev @ x_dev)
    if den == 0:
        return float("nan")
    return float(num / den)


def add_spatial_features(
    gdf: gpd.GeoDataFrame,
    score_column: str = "market_potential_score",
    compute_morans: bool = True,
) -> tuple[gpd.GeoDataFrame, float | None]:
    """Add spatial lag column and optionally compute Moran's I."""
    out = gdf.copy()
    lag_col = "spatial_lag_score" if score_column in out.columns else "mean_night_light"
    out["spatial_lag_score"] = compute_spatial_lag(out, column=lag_col)
    morans = compute_morans_i(out, column=score_column) if compute_morans else None
    if morans is not None:
        logger.info("Moran's I (%s) = %.4f", score_column, morans)
    return out, morans
