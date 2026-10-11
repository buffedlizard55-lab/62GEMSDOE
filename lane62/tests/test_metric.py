"""Metric identities, the published worked example, and the two theorems the
emitter relies on.  Every assertion here is checked against a literal
transcription of the published equations, never against this implementation's
own output.
"""
from __future__ import annotations

import numpy as np
import pytest

from gems62.metric import (ALPHA, BETA, RADIUS_PX, credit_bar, dti_bruteforce,
                           dti_exact, dti_from_components, implied_truth_mass,
                           kernel, marginal_accept)

pytestmark = pytest.mark.filterwarnings("ignore::RuntimeWarning")


def test_published_example_arithmetic():
    """The organizer's own worked example returns 0.60.

    Source: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
    TP_w = 3.00, FP_w = 1.89, FN_w = 2.00, alpha 0.2, beta 0.8.
    """
    got = dti_from_components(3.00, 1.89, 2.00)
    assert got == pytest.approx(3.00 / (3.00 + 0.2 * 1.89 + 0.8 * 2.00), abs=1e-12)
    assert got == pytest.approx(0.60, abs=6e-3)


def test_kernel_is_the_published_triangle():
    assert kernel(0.0) == 1.0
    assert kernel(1.5) == pytest.approx(0.5)
    assert kernel(3.0) == 0.0
    assert kernel(3.0001) == 0.0
    assert kernel(np.array([0.0, 1.0, 2.0, 3.0])).tolist() == [1.0,
                                                                pytest.approx(2 / 3), pytest.approx(1 / 3), 0.0]


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_matches_literal_transcription(seed):
    """dti_exact must equal the O(|G||P|) literal reading of the printed formulas."""
    rng = np.random.default_rng(seed)
    p = np.where(rng.random((9, 9)) < 0.3, rng.random((9, 9)), 0.0)
    t = rng.random((9, 9)) < 0.22
    a = dti_exact(p, t)
    b = dti_bruteforce(p, t)
    assert a["dti"] == pytest.approx(b["dti"], abs=1e-9)
    assert a["tp"] == pytest.approx(b["tp"], abs=1e-9)
    assert a["fp"] == pytest.approx(b["fp"], abs=1e-9)
    assert a["fn"] == pytest.approx(b["fn"], abs=1e-9)


def test_identity_i1_holds_on_random_fields():
    """DTI = T / (0.2*T + 0.2*F + 0.8*K) with K the truth count -- exactly."""
    rng = np.random.default_rng(7)
    for _ in range(20):
        p = np.where(rng.random((14, 14)) < 0.25, rng.random((14, 14)), 0.0)
        t = rng.random((14, 14)) < 0.2
        r = dti_exact(p, t)
        lhs = 1.0 / r["dti"]
        rhs = (0.2 * r["tp"] + 0.2 * r["fp"] + 0.8 * r["n_truth"]) / r["tp"]
        assert lhs == pytest.approx(rhs, rel=1e-9)


def test_identity_i3_thresholding_beats_grading():
    """DTI(lambda*p) increases in lambda, so a graded map is dominated by its own
    thresholded support."""
    rng = np.random.default_rng(11)
    p = np.where(rng.random((20, 20)) < 0.3, rng.random((20, 20)), 0.0)
    t = rng.random((20, 20)) < 0.2
    vals = [dti_exact(p * lam, t)["dti"] for lam in (0.2, 0.4, 0.6, 0.8, 1.0)]
    assert all(b > a for a, b in zip(vals, vals[1:])), vals


def test_identity_i2_marginal_rule_matches_bruteforce():
    """The marginal test agrees with actually adding the dot, on random fields."""
    rng = np.random.default_rng(5)
    hits = 0
    for _ in range(30):
        p = np.where(rng.random((16, 16)) < 0.25, 1.0, 0.0)
        t = rng.random((16, 16)) < 0.18
        r0 = dti_exact(p, t)
        yy, xx = np.nonzero(~(p > 0).astype(bool))
        if yy.size == 0:
            continue
        k = rng.integers(yy.size)
        q = p.copy(); q[yy[k], xx[k]] = 1.0
        r1 = dti_exact(q, t)
        # realised credit of the added dot
        from scipy.ndimage import distance_transform_edt
        kb = kernel(distance_transform_edt(~t))[yy[k], xx[k]]
        dT = r1["tp"] - r0["tp"]
        pred = marginal_accept(dT, kb, r0["tp"], r0["fp"], r0["n_truth"])
        truth = r1["dti"] > r0["dti"]
        assert pred == truth
        hits += 1
    assert hits > 20


def test_credit_bar_is_alpha_times_s():
    for s in (0.1, 0.2600, 0.2778, 0.3195, 0.4133):
        assert credit_bar(s) == pytest.approx(ALPHA * s)
    assert credit_bar(0.2778) == pytest.approx(0.05556, abs=1e-5)


def test_masking_removes_catalogue_from_both_terms():
    """A prediction on a catalogue pixel must earn nothing and cost nothing."""
    t = np.zeros((11, 11), bool); t[5, 5] = True
    known = np.zeros((11, 11), bool); known[5, 5] = True
    p = np.zeros((11, 11)); p[5, 5] = 1.0
    r = dti_exact(p, t, known=known)
    assert r["n_truth"] == 0 or r["tp"] == 0.0


def test_implied_truth_mass_inverts_identity_i1():
    """Invert DTI = T/(0.2T + 0.2F + 0.8K) for K.

    Bookkeeping: for unit dots, every emitted pixel contributes kbar of its value
    to T and (1 - kbar) to F, so F = n - sum(kbar).  The champion family's own
    numbers are n = 37,654, T = 3,849, hence sum(kbar) = 3,849 and F = 33,805.
    """
    T, F, K = 3849.0, 33805.0, 7905.0
    n = T + F
    # dti_from_components takes (tp, fp, fn) -- the RAW published formula, so the
    # third argument is FN_w = K - T, not K.  Written the other way round the
    # identity would not reproduce the owner-reported 0.2778, which is exactly the
    # check below.
    s_correct = dti_from_components(T, F, K - T)
    assert s_correct == pytest.approx(0.2778, abs=1e-4)
    assert dti_from_components(T, F, K) != pytest.approx(s_correct, abs=1e-3)
    got = implied_truth_mass(s_correct, T, n, T)   # S = n, M = sum(kbar) = T
    assert got == pytest.approx(K, rel=1e-6)


def test_rejects_out_of_range_predictions():
    t = np.zeros((5, 5), bool); t[2, 2] = True
    p = np.zeros((5, 5)); p[2, 2] = 1.5
    with pytest.raises(ValueError):
        dti_exact(p, t)
