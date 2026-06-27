"""Edge-case tests for fixed-shape ML feature extraction."""

import numpy as np

from ml.features import COMBINED_FEATURE_COUNT, batch_extract_features, extract_features


def test_extract_features_handles_nulls_special_text_and_extreme_amounts() -> None:
    samples = [
        {},
        {"merchant": None, "description": None, "amount": None, "transaction_type": None},
        {"merchant": "₹ café / दुकान", "description": "!@#$%^&*()", "amount": 0},
        {"merchant": "x" * 10000, "description": "y" * 20000, "amount": 10**100},
    ]
    for sample in samples:
        features = extract_features(sample)
        assert isinstance(features, np.ndarray)
        assert features.shape == (COMBINED_FEATURE_COUNT,)
        assert np.isfinite(features).all()


def test_batch_extract_features_has_stable_shape() -> None:
    assert batch_extract_features([]).shape == (0, COMBINED_FEATURE_COUNT)
    matrix = batch_extract_features([{"description": f"unseen words {index}", "amount": index} for index in range(100)])
    assert matrix.shape == (100, COMBINED_FEATURE_COUNT)
    assert np.isfinite(matrix).all()
