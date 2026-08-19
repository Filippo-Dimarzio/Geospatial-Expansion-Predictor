"""Data acquisition subpackage."""

from market_predictor.data.features import add_road_network_access, add_synthetic_features
from market_predictor.data.mock import generate_mock_data
from market_predictor.data.real import generate_real_data

__all__ = [
    "generate_mock_data",
    "generate_real_data",
    "add_synthetic_features",
    "add_road_network_access",
]
