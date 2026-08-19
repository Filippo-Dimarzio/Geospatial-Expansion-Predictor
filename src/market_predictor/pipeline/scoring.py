"""Market potential scoring: weighted, MCDA, PCA, ML."""

from __future__ import annotations

import logging
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd

logger = logging.getLogger("market_predictor.pipeline.scoring")

ScoreMethod = str  # weighted | mcda | pca | ml


def _min_max_normalize(series: pd.Series) -> pd.Series:
    lo, hi = series.min(), series.max()
    if hi == lo:
        return series.apply(lambda _: 0.5)
    return (series - lo) / (hi - lo)


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Normalize feature weights to sum to 1 (absolute values for mixed signs)."""
    total = sum(abs(v) for v in weights.values())
    if total == 0:
        n = len(weights)
        return {k: 1.0 / n for k in weights}
    return {k: v / total for k, v in weights.items()}


def calculate_market_potential_score(
    gdf: gpd.GeoDataFrame,
    light_weight: float = 0.6,
    population_weight: float = 0.4,
    light_column: str = "mean_night_light",
    population_column: str = "population_density",
    normalize_weight_sum: bool = True,
    method: ScoreMethod = "weighted",
    feature_weights: dict[str, float] | None = None,
    spatial_lag_column: str | None = "spatial_lag_score",
    spatial_lag_weight: float = 0.0,
) -> gpd.GeoDataFrame:
    """
    Compute market potential score using the selected method.
    Weights are explicitly normalized when normalize_weight_sum=True.
    """
    out = gdf.copy()

    if method == "weighted":
        lw, pw = light_weight, population_weight
        if normalize_weight_sum and (lw + pw) > 0:
            total = lw + pw
            lw, pw = lw / total, pw / total
        out["normalized_light"] = _min_max_normalize(out[light_column])
        out["normalized_population"] = _min_max_normalize(out[population_column])
        score = out["normalized_light"] * lw + out["normalized_population"] * pw

    elif method == "mcda":
        fw = normalize_weights(feature_weights or {})
        score = pd.Series(0.0, index=out.index)
        for col, w in fw.items():
            if col not in out.columns:
                logger.warning("MCDA column %s missing; skipping", col)
                continue
            norm = _min_max_normalize(out[col].astype(float))
            if w < 0:
                norm = 1 - norm  # invert penalty features (e.g. competitor_count)
                w = abs(w)
            score += norm * w

    elif method == "pca":
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler

        cols = [c for c in (feature_weights or {}).keys() if c in out.columns]
        if len(cols) < 2:
            cols = [light_column, population_column]
        X = StandardScaler().fit_transform(out[cols].astype(float).fillna(0))
        pc1 = PCA(n_components=1).fit_transform(X).flatten()
        score = pd.Series(_min_max_normalize(pd.Series(pc1)), index=out.index)

    elif method == "ml":
        score = _ml_score(out, light_column, population_column)

    else:
        raise ValueError(f"Unknown scoring method: {method}")

    if spatial_lag_column and spatial_lag_column in out.columns and spatial_lag_weight > 0:
        lag = _min_max_normalize(out[spatial_lag_column])
        score = score * (1 - spatial_lag_weight) + lag * spatial_lag_weight

    out["market_potential_score"] = score.round(4)
    return out


def _ml_score(gdf: gpd.GeoDataFrame, light_col: str, pop_col: str) -> pd.Series:
    """
    Simple XGBoost regressor trained on synthetic store performance.
    Replace y with real store revenue/orders when available.
    """
    try:
        from xgboost import XGBRegressor
    except ImportError:
        logger.warning("xgboost not installed; falling back to weighted score")
        nl = _min_max_normalize(gdf[light_col])
        np_ = _min_max_normalize(gdf[pop_col])
        return nl * 0.6 + np_ * 0.4

    feature_cols = [
        c
        for c in [
            light_col,
            pop_col,
            "median_income",
            "road_access_score",
            "competitor_count",
            "delivery_radius_km",
        ]
        if c in gdf.columns
    ]
    X = gdf[feature_cols].astype(float).fillna(0)
    rng = np.random.default_rng(0)
    y = (
        X[light_col] * 0.4
        + X[pop_col] * 0.003
        + rng.normal(0, 5, len(X))
    )
    model = XGBRegressor(n_estimators=50, max_depth=3, random_state=0)
    model.fit(X, y)
    preds = model.predict(X)
    return pd.Series(_min_max_normalize(pd.Series(preds)), index=gdf.index)


def train_ml_model(
    gdf: gpd.GeoDataFrame,
    target_column: str,
    feature_columns: list[str] | None = None,
) -> Any:
    """Train and return an XGBoost model for production use."""
    from xgboost import XGBRegressor

    cols = feature_columns or [
        c
        for c in gdf.columns
        if c not in ("geometry", target_column, "district_id") and gdf[c].dtype != "object"
    ]
    X = gdf[cols].astype(float).fillna(0)
    y = gdf[target_column].astype(float)
    model = XGBRegressor(n_estimators=100, max_depth=4, random_state=0)
    model.fit(X, y)
    return model
