"""Tests for opportunity detection."""

import geopandas as gpd
from shapely.geometry import box

from market_predictor.pipeline.opportunity import identify_high_potential_zones
from market_predictor.pipeline.scoring import calculate_market_potential_score


def _make_gdf(n=20):
    records = []
    for i in range(n):
        records.append({
            "district_id": f"D-{i:03d}",
            "geometry": box(i, i, i + 1, i + 1),
            "mean_night_light": 10 + i * 4,
            "population_density": 1000 + i * 200,
            "current_business_count": i,
        })
    # Force 3 high-light low-business districts
    records[-1]["current_business_count"] = 1
    records[-2]["current_business_count"] = 2
    records[-3]["current_business_count"] = 1
    return gpd.GeoDataFrame(records, crs="EPSG:4326")


def test_opportunity_detection_finds_underserved():
    gdf = _make_gdf()
    scored = calculate_market_potential_score(gdf)
    result = identify_high_potential_zones(scored, business_density_percentile=40, market_potential_percentile=60)
    flagged = result[result["is_high_potential_untapped"]]
    assert len(flagged) >= 1
    assert flagged["opportunity_rank"].notna().all()
    assert flagged["opportunity_rank"].min() == 1


def test_score_cutoff_stored():
    gdf = _make_gdf()
    scored = calculate_market_potential_score(gdf)
    result = identify_high_potential_zones(scored)
    assert "score_cutoff" in result.columns
    assert result["score_cutoff"].iloc[0] > 0
