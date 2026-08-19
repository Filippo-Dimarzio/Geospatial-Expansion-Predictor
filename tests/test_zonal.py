"""Tests for zonal statistics on tiny fixture."""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from shapely.geometry import box

from market_predictor.pipeline.zonal import extract_zonal_statistics

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def tiny_raster(tmp_path_factory):
    d = tmp_path_factory.mktemp("raster")
    path = d / "tiny.tif"
    arr = np.array([[10, 20], [30, 40]], dtype=np.float32)
    transform = from_bounds(0, 0, 2, 2, 2, 2)
    with rasterio.open(
        path, "w", driver="GTiff", height=2, width=2, count=1,
        dtype=arr.dtype, crs="EPSG:4326", transform=transform,
    ) as dst:
        dst.write(arr, 1)
    return path


@pytest.fixture(scope="module")
def tiny_districts():
    gdf = gpd.GeoDataFrame(
        {
            "district_id": ["A", "B"],
            "geometry": [box(0, 0, 1, 1), box(1, 0, 2, 1)],
        },
        crs="EPSG:4326",
    )
    return gdf


def test_zonal_mean_manual(tiny_raster, tiny_districts):
    result = extract_zonal_statistics(tiny_districts, str(tiny_raster), backend="manual")
    assert "mean_night_light" in result.columns
    assert result["mean_night_light"].notna().all()
    # Values should fall within the raster range [10, 40]
    assert result["mean_night_light"].between(10, 40).all()
    assert result.loc[0, "mean_night_light"] != result.loc[1, "mean_night_light"]


def test_zonal_rasterstats(tiny_raster, tiny_districts):
    pytest.importorskip("rasterstats")
    result = extract_zonal_statistics(tiny_districts, str(tiny_raster), backend="rasterstats")
    assert result["mean_night_light"].notna().all()
