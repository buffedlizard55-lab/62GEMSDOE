"""Regression tests for the exact DTI implementation.

Each test cites the published or prior-repository source of the identity it checks.
Run with:  python -m pytest tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems62.metric import (  # noqa: E402
    ALPHA,
    BETA,
    EPS,
    brute_force_components,
    dti_components,
    maximum_useful_distance_m,
    unit_dot_dti,
)


def test_official_worked_example():
    """Official worked example: TP=3.00, FP=1.89, FN=2.00 -> 0.60266 (page rounds to 0.60).

    Source: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
    ("# Mathematical representation").
    """
    assert ALPHA == 0.2 and BETA == 0.8
    value = 3.00 / (3.00 + 0.2 * 1.89 + 0.8 * 2.00)
    assert round(value, 2) == 0.60
    assert value == pytest.approx(0.6026517, abs=1e-6)


def test_one_by_five_counterexample():
    """1x5 counterexample: truth at columns 1,2; one prediction at column 1.

    R = 3 m, 1 m pixels -> TP_w = 5/3, FP_w = 0, FN_w = 1/3, DTI = 25/29.

    Source: GEMSDOE48 research erratum ``metric-identity-erratum-20261007.md``,
    which uses this case to show that ``FP_w = S - TP_w`` is false in general.
    """
    pred = np.zeros((1, 5))
    truth = np.zeros((1, 5), dtype=bool)
    pred[0, 1] = 1.0  # the prediction sits ON truth column 1
    truth[0, 1] = truth[0, 2] = True

    c = dti_components(pred, truth, pixel_size_m=1.0, radius_m=3.0)
    assert c.tp_w == pytest.approx(5.0 / 3.0)
    assert c.fp_w == pytest.approx(0.0)
    assert c.fn_w == pytest.approx(1.0 / 3.0)
    assert c.dti == pytest.approx(25.0 / 29.0, abs=1e-12)


def test_perfect_prediction_scores_one():
    truth = np.zeros((40, 40), dtype=bool)
    truth[10:30, 20] = True
    c = dti_components(truth.astype(float), truth)
    assert c.dti == pytest.approx(1.0, abs=1e-9)
    assert c.fp_w == pytest.approx(0.0)


def test_empty_prediction_scores_zero():
    truth = np.zeros((40, 40), dtype=bool)
    truth[10:30, 20] = True
    c = dti_components(np.zeros((40, 40)), truth)
    assert c.dti == pytest.approx(0.0, abs=1e-12)
    assert c.fn_w == pytest.approx(20.0)


def test_non_overlapping_unit_dot_closed_form_matches_exact_metric():
    """``unit_dot_dti`` must reproduce the exact metric for well-separated dots."""
    rng = np.random.default_rng(0)
    truth = np.zeros((200, 200), dtype=bool)
    # A diagonal truth trace.
    for i in range(20, 180):
        truth[i, i] = True

    n = 12
    dots = np.zeros((200, 200))
    ys = np.linspace(25, 174, n).round().astype(int)
    for y in ys:
        dots[y, y] = 1.0
        dots[y, y + 1] = 1.0  # 100 m wide marker so credit is not sub-pixel

    c = dti_components(dots, truth)
    assert c.tp_w > 0.0
    # Closed form with FP_w = M - T.
    closed = unit_dot_dti(int(dots.sum()), c.tp_w / dots.sum(), float(truth.sum()))
    assert closed == pytest.approx(c.dti, rel=0.05)


def test_fast_path_matches_brute_force():
    rng = np.random.default_rng(7)
    truth = rng.random((60, 60)) < 0.05
    pred = np.zeros((60, 60))
    idx = rng.choice(3600, size=25, replace=False)
    pred.flat[idx] = 1.0

    fast = dti_components(pred, truth)
    slow = brute_force_components(pred, truth)
    assert fast.tp_w == pytest.approx(slow.tp_w, abs=1e-9)
    assert fast.fp_w == pytest.approx(slow.fp_w, abs=1e-9)
    assert fast.fn_w == pytest.approx(slow.fn_w, abs=1e-9)
    assert fast.dti == pytest.approx(slow.dti, abs=1e-12)


def test_rejects_out_of_range_and_nan_inside_footprint():
    truth = np.zeros((10, 10), dtype=bool)
    truth[5, 5] = True
    valid = np.ones((10, 10), dtype=bool)

    bad = np.zeros((10, 10))
    bad[1, 1] = 1.5
    with pytest.raises(ValueError, match=r"outside \[0,1\]"):
        dti_components(bad, truth, valid=valid)

    nan = np.zeros((10, 10))
    nan[1, 1] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        dti_components(nan, truth, valid=valid)


def test_valid_mask_excludes_predictions_outside_the_footprint():
    """Predictions outside the scored footprint enter no term."""
    truth = np.zeros((10, 10), dtype=bool)
    truth[5, 5] = True
    valid = np.zeros((10, 10), dtype=bool)
    valid[4:7, 4:7] = True

    inside = np.zeros((10, 10))
    inside[5, 5] = 1.0
    outside = inside.copy()
    outside[0, 0] = 1.0

    a = dti_components(inside, truth, valid=valid)
    b = dti_components(outside, truth, valid=valid)
    assert a.dti == pytest.approx(b.dti)
    assert a.fp_w == pytest.approx(b.fp_w)


def test_marginal_rule_threshold():
    """At DTI = 0.28 the profit bar is 283 m, the value cited in the lane analysis."""
    d = maximum_useful_distance_m(0.2778)
    assert d == pytest.approx(283.32, abs=0.05)


def test_larger_value_never_hurts_a_fixed_support():
    """For a fixed dot support, DTI is strictly increasing in the dot value."""
    truth = np.zeros((80, 80), dtype=bool)
    truth[30:50, 40] = True
    support = np.zeros((80, 80))
    for y in range(30, 50, 2):
        support[y, 40] = 1.0

    values = [dti_components(support * v, truth).dti for v in (0.2, 0.5, 0.8, 1.0)]
    assert values == sorted(values)
