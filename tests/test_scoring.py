"""Tests for scoring normalization."""

import pandas as pd

from market_predictor.pipeline.scoring import _min_max_normalize, normalize_weights


def test_min_max_normalize_range():
    s = pd.Series([0, 50, 100])
    out = _min_max_normalize(s)
    assert out.min() == 0.0
    assert out.max() == 1.0
    assert out.iloc[1] == 0.5


def test_min_max_normalize_constant():
    s = pd.Series([5, 5, 5])
    out = _min_max_normalize(s)
    assert (out == 0.5).all()


def test_normalize_weights():
    w = normalize_weights({"a": 0.6, "b": 0.4})
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_normalize_weights_negative():
    w = normalize_weights({"a": 0.5, "b": -0.5})
    assert abs(sum(abs(v) for v in w.values()) - 1.0) < 1e-9
