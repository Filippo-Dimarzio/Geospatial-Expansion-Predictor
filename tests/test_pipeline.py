"""End-to-end pipeline smoke test."""

import numpy as np
import rasterio
from rasterio.transform import xy

from market_predictor.data.mock import generate_mock_data
from market_predictor.pipeline.runner import run_pipeline


def test_united_states_mock_data_stays_in_us_bbox(tmp_path):
    raster = tmp_path / "us_night_lights.tif"
    districts = tmp_path / "us_districts.geojson"
    generate_mock_data(raster_path=raster, districts_path=districts, region="united_states")

    with rasterio.open(raster) as src:
        arr = src.read(1)
        row, col = np.unravel_index(arr.argmax(), arr.shape)
        lon, lat = xy(src.transform, row, col, offset="center")

    assert -125 < lon < -66
    assert 24 < lat < 50
    assert arr.max() > 40


def test_pipeline_end_to_end(tmp_path):
    raster = tmp_path / "night_lights.tif"
    districts = tmp_path / "districts.geojson"
    generate_mock_data(raster_path=raster, districts_path=districts)

    from market_predictor.config import AppConfig

    cfg = AppConfig.load(overrides={
        "data": {"districts_path": str(districts), "raster_path": str(raster)},
        "pipeline": {"persist_outputs": False},
    })
    result = run_pipeline(config=cfg)
    assert len(result) == 144  # 12x12 grid
    assert "market_potential_score" in result.columns
    assert result["is_high_potential_untapped"].any()
