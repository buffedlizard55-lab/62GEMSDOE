"""Spatial-block CI regression tests for the holdout instrument."""
from __future__ import annotations

from scripts.run_holdout import block_bootstrap_dti_ci


def test_fold_cluster_bootstrap_is_reproducible_and_bounded():
    folds = [
        {"tp": 12.0, "fp": 20.0, "fn": 80.0},
        {"tp": 0.0, "fp": 0.0, "fn": 40.0},
        {"tp": 3.0, "fp": 6.0, "fn": 97.0},
        {"tp": 0.0, "fp": 0.0, "fn": 50.0},
    ]
    ci1 = block_bootstrap_dti_ci(folds, replicates=1000, seed=62)
    ci2 = block_bootstrap_dti_ci(folds, replicates=1000, seed=62)
    assert ci1 == ci2
    assert ci1 is not None and len(ci1) == 2
    assert 0.0 <= ci1[0] <= ci1[1] <= 1.0


def test_fold_cluster_bootstrap_requires_multiple_blocks():
    assert block_bootstrap_dti_ci([{"tp": 1, "fp": 0, "fn": 1}]) is None
