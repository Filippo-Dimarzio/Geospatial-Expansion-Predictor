"""High-potential untapped zone detection."""

from __future__ import annotations

import geopandas as gpd
import numpy as np


def identify_high_potential_zones(
    gdf: gpd.GeoDataFrame,
    business_density_percentile: float = 40,
    market_potential_percentile: float = 70,
    business_column: str = "current_business_count",
    score_column: str = "market_potential_score",
) -> gpd.GeoDataFrame:
    out = gdf.copy()
    business_cutoff = np.percentile(out[business_column], business_density_percentile)
    score_cutoff = np.percentile(out[score_column], market_potential_percentile)

    out["is_high_potential_untapped"] = (out[business_column] <= business_cutoff) & (
        out[score_column] >= score_cutoff
    )
    out["business_cutoff"] = business_cutoff
    out["score_cutoff"] = score_cutoff

    out["opportunity_rank"] = np.nan
    flagged = out[out["is_high_potential_untapped"]].sort_values(score_column, ascending=False)
    out.loc[flagged.index, "opportunity_rank"] = range(1, len(flagged) + 1)
    return out
