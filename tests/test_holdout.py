"""The holdout must be spatially blocked, must mask the visible catalogue, and
must not report an interval that excludes its own point estimate (the defect
logged as IR-62-09).
"""
from __future__ import annotations

import numpy as np
import pytest

from gems62 import grid as G
from gems62 import holdout as H
from gems62.metric import dti_exact


@pytest.fixture(scope="module")
def grid():
    return G.load_grid(".")


def test_block_folds_partition_the_grid():
    f = H.block_folds((10, 10), 2, 2)
    assert f.shape == (10, 10)
    assert sorted(np.unique(f).tolist()) == [0, 1, 2, 3]
    assert np.array_equal(np.unique(f, return_counts=True)[1], np.array([25, 25, 25, 25]))


def test_segments_drops_specks_and_keeps_labels_consistent(grid):
    lab, ids = H.segments(grid.catalogue, min_px=50)
    assert ids.size > 100
    sizes = np.bincount(lab.ravel())
    assert (sizes[ids] >= 50).all()
    assert sizes[0] == int((lab == 0).sum())


def test_hide_and_recover_withholds_around_the_block(grid):
    pred = grid.catalogue.copy()           # a perfect answer on the visible data
    r = H.hide_and_recover(pred, grid.catalogue, grid.footprint, rows=2, cols=2)
    assert r["n_truth_px"] > 0
    assert r["pooled"]["n_truth"] == r["n_truth_px"]
    # the withheld set is disjoint from the visible set by construction
    assert r["pooled"]["n_predicted"] > 0


def test_bootstrap_interval_brackets_the_pooled_value(grid):
    """IR-62-09: the interval must be the interval OF the reported number."""
    rng = np.random.default_rng(21)
    pred = np.zeros(grid.footprint.shape, bool)
    idx = rng.choice(np.flatnonzero(grid.active.ravel()), 4000, replace=False)
    pred.ravel()[idx] = True
    # a small synthetic truth so the test is fast but the identity still binds
    truth = np.zeros_like(pred)
    j = rng.choice(idx, 600, replace=False)
    truth.ravel()[j] = True
    pooled = dti_exact(pred.astype(float), truth, valid=grid.footprint,
                       known=grid.catalogue)["dti"]
    lo, hi = H.bootstrap_dti_ci(pred, truth, grid.footprint, grid.catalogue, n_boot=200)
    assert lo <= pooled <= hi, (lo, pooled, hi)


def test_bootstrap_raises_if_the_estimator_disagrees(grid):
    """The fail-closed guard must actually fire when the algebra is broken."""
    import gems62.holdout as HH
    import gems62.metric as M
    rng = np.random.default_rng(3)
    pred = np.zeros(grid.footprint.shape, bool)
    idx = rng.choice(np.flatnonzero(grid.active.ravel()), 500, replace=False)
    pred.ravel()[idx] = True
    truth = np.zeros_like(pred)
    truth.ravel()[idx[:80]] = True
    orig = M.dti_exact
    try:
        M.dti_exact = lambda *a, **k: dict(dti=0.123456)      # deliberately wrong
        with pytest.raises(AssertionError):
            HH.bootstrap_dti_ci(pred, truth, grid.footprint, grid.catalogue, n_boot=10)
    finally:
        M.dti_exact = orig


def test_feature_auc_is_one_for_a_perfect_feature(grid):
    truth = np.zeros(grid.footprint.shape, bool)
    idx = np.flatnonzero(grid.active.ravel())[:500]
    truth.ravel()[idx] = True
    perfect = truth.astype(float)
    auc = H.feature_auc(perfect, truth, grid.active, n_sample=20000, seed=0)
    assert auc == pytest.approx(1.0, abs=1e-9)
    assert H.feature_auc(-perfect, truth, grid.active, n_sample=20000, seed=0) == pytest.approx(0.0, abs=1e-9)
