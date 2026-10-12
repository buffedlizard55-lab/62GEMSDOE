"""Cross-check exp6's fast binary DTI against the repository's tested metric implementation.

`scripts/exp6_detector_blocked.py::dti_binary_fast` replaces the 49-shift transcription with one
Euclidean distance transform per field.  Same published index, different arithmetic route, so the
identity is asserted here on random fields rather than trusted.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from gems62.metric import dti_components  # noqa: E402

spec = importlib.util.spec_from_file_location("exp6", ROOT / "scripts" / "exp6_detector_blocked.py")
exp6 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exp6)


def _random_case(seed: int, n_truth: int = 40, n_pred: int = 60, shape=(60, 80)):
    rng = np.random.default_rng(seed)
    truth = np.zeros(shape, bool)
    pred = np.zeros(shape, bool)
    ty = rng.integers(0, shape[0], n_truth)
    tx = rng.integers(0, shape[1], n_truth)
    truth[ty, tx] = True
    py = rng.integers(0, shape[0], n_pred)
    px = rng.integers(0, shape[1], n_pred)
    pred[py, px] = True
    active = np.ones(shape, bool)
    return pred, truth, active


def test_fast_matches_reference_implementation():
    for seed in range(6):
        pred, truth, active = _random_case(seed)
        ref = dti_components(pred.astype(np.float64), truth, valid=active,
                             pixel_size_m=100.0, radius_m=300.0)
        got = exp6.dti_binary_fast(pred.astype(np.float64),
                                   {"S": (exp6.kernel_field(truth), truth, float(truth.sum()))},
                                   active)["S"]
        # kernel_field is float32 (12.3 M-cell grids); the reference is float64.  Agreement to
        # 1e-5 absolute is exactness at this precision, not an approximation.
        assert abs(got["T"] - ref.tp_w) < 1e-5, (seed, got["T"], ref.tp_w)
        assert abs(got["F"] - ref.fp_w) < 1e-5, (seed, got["F"], ref.fp_w)
        assert abs(got["K"] - float(truth.sum())) < 1e-12
        assert abs(got["dti"] - ref.dti) < 1e-8, (seed, got["dti"], ref.dti)


def test_hard_core_separation_is_beyond_the_kernel_radius():
    rng = np.random.default_rng(0)
    score = rng.random((120, 140), dtype=np.float32)
    elig = np.ones(score.shape, bool)
    keep = exp6.hard_core_local_maxima(score, elig, n_want=400)
    ys, xs = np.nonzero(keep)
    d = np.hypot(ys[:, None] - ys[None, :], xs[:, None] - xs[None, :])
    np.fill_diagonal(d, np.inf)
    assert keep.sum() > 0
    assert d.min() > 3.0, f"two emitted dots share a 300 m kernel: {d.min()}"


def test_hard_core_respects_eligibility_and_mass_target():
    rng = np.random.default_rng(1)
    score = rng.random((80, 90), dtype=np.float32)
    elig = np.zeros(score.shape, bool)
    elig[10:70, 10:80] = True
    keep = exp6.hard_core_local_maxima(score, elig, n_want=50)
    assert int(keep.sum()) == 50
    assert np.all(elig[keep])
