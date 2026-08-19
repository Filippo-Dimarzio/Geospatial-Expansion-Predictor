"""Sensitivity analysis across weight ranges."""

from __future__ import annotations

import logging

import geopandas as gpd
import numpy as np
import pandas as pd

from market_predictor.pipeline.opportunity import identify_high_potential_zones
from market_predictor.pipeline.scoring import calculate_market_potential_score

logger = logging.getLogger("market_predictor.pipeline.sensitivity")


def run_sensitivity_analysis(
    gdf: gpd.GeoDataFrame,
    light_weight_range: tuple[float, float] = (0.2, 0.8),
    n_steps: int = 7,
    business_density_percentile: float = 40,
    market_potential_percentile: float = 70,
) -> pd.DataFrame:
    """
    Sweep light_weight from min to max and record rank stability per district.
    Returns a DataFrame with columns: district_id, light_weight, rank, score, is_flagged.
    """
    lo, hi = light_weight_range
    weights = np.linspace(lo, hi, n_steps)
    records = []
    for lw in weights:
        pw = 1.0 - lw
        scored = calculate_market_potential_score(gdf, light_weight=lw, population_weight=pw)
        flagged = identify_high_potential_zones(
            scored,
            business_density_percentile=business_density_percentile,
            market_potential_percentile=market_potential_percentile,
        )
        ranked = flagged.sort_values("market_potential_score", ascending=False).reset_index(drop=True)
        ranked["rank"] = range(1, len(ranked) + 1)
        for _, row in ranked.iterrows():
            records.append(
                {
                    "district_id": row["district_id"],
                    "light_weight": round(lw, 3),
                    "population_weight": round(pw, 3),
                    "rank": row["rank"],
                    "market_potential_score": row["market_potential_score"],
                    "is_high_potential_untapped": row["is_high_potential_untapped"],
                }
            )
    return pd.DataFrame(records)


def rank_stability_summary(sensitivity_df: pd.DataFrame) -> pd.DataFrame:
    """Summarize how often each district stays in top-N across weight sweeps."""
    summary = (
        sensitivity_df.groupby("district_id")
        .agg(
            mean_rank=("rank", "mean"),
            rank_std=("rank", "std"),
            mean_score=("market_potential_score", "mean"),
            flagged_fraction=("is_high_potential_untapped", "mean"),
        )
        .reset_index()
    )
    summary["rank_std"] = summary["rank_std"].fillna(0)
    return summary.sort_values("mean_rank")
