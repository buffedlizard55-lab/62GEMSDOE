"""IR-62-13 / IR-62-18 — the promoted holdout evaluator must equal the original.

The segmented hide-and-recover evaluator existed three times in this repository with three
different APIs.  It is now promoted to ``src/gems62/holdout_segmented.py``, and this test
executes **both** copies on one synthetic fixture and asserts that they produce identical
pooled numbers, so the promotion cannot silently drift.  The original copy is loaded through
``importlib`` under an alias rather than being copied or edited in place.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems62 import holdout_segmented as promoted  # noqa: E402


def _load_lane_copy():
    """Load ``lane62-h62a/src/gems62`` under the alias ``gems62h62a``."""
    pkg_dir = ROOT / "lane62-h62a" / "src" / "gems62"
    if not (pkg_dir / "holdout.py").exists():
        pytest.skip("lane62-h62a copy not present in this checkout")
    spec = importlib.util.spec_from_file_location(
        "gems62h62a", pkg_dir / "__init__.py",
        submodule_search_locations=[str(pkg_dir)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gems62h62a"] = mod
    spec.loader.exec_module(mod)
    return importlib.import_module("gems62h62a.holdout")


@pytest.fixture()
def fixture():
    """A synthetic scene: three catalogue traces, a footprint, and a simple emitter."""
    shape = (140, 180)
    cat = np.zeros(shape, bool)
    cat[30, 10:170] = True
    cat[70, 10:170] = True
    cat[110, 10:170] = True
    footprint = np.ones(shape, bool)
    footprint[:5, :] = False
    footprint[-5:, :] = False

    def emit_fn(eligible, priority, footprint_, visible_catalogue, budget):
        # a deterministic, catalogue-independent emitter: the top `budget` priorities in
        # the eligible domain, thinned by a 3 px hard core
        from gems62.metric import RADIUS_PX
        p = np.where(eligible, priority, -np.inf)
        flat = p.ravel()
        order = np.argsort(-flat, kind="stable")[: budget * 8]
        order = order[np.isfinite(flat[order])]
        out = np.zeros(shape, bool)
        taken = 0
        ys, xs = np.divmod(order, shape[1])
        r = int(np.ceil(RADIUS_PX))
        for y, x in zip(ys, xs):
            if out[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1].any():
                continue
            out[y, x] = True
            taken += 1
            if taken >= budget:
                break
        return out

    rng = np.random.default_rng(5)
    priority = rng.random(shape)
    eligible = footprint & ~cat
    return dict(eligible=eligible, priority=priority, footprint=footprint,
                catalogue=cat, emission_fn=emit_fn)


def _run(mod, fx, **kw):
    return mod.run_holdout(fx["eligible"], fx["priority"], fx["footprint"], fx["catalogue"],
                           fx["emission_fn"], n_folds=2, seeds=(20, 21), controls=False,
                           budget=120, **kw)


def test_promoted_equals_original(fixture):
    lane = _load_lane_copy()
    a = _run(promoted, fixture)
    b = _run(lane, fixture)
    assert a["version"] == b["version"] == promoted.HOLDOUT_VERSION
    assert a["pooled_dti"] == pytest.approx(b["pooled_dti"], rel=0, abs=0)
    assert a["pooled_tp"] == pytest.approx(b["pooled_tp"], rel=0, abs=0)
    assert a["pooled_fp"] == pytest.approx(b["pooled_fp"], rel=0, abs=0)
    assert a["pooled_fn"] == pytest.approx(b["pooled_fn"], rel=0, abs=0)
    assert a["withheld_positives_total"] == b["withheld_positives_total"]
    assert a["n_folds"] == b["n_folds"]


def test_metric_keyword_path_is_the_documented_composition():
    """``dti_binary(valid=, known=)`` must equal ``dti_binary(active=valid & ~known)``."""
    from gems62.metric import dti_binary
    rng = np.random.default_rng(3)
    pred = rng.random((60, 60)) > 0.97
    truth = rng.random((60, 60)) > 0.99
    valid = rng.random((60, 60)) > 0.1
    known = rng.random((60, 60)) > 0.9
    kw = dti_binary(pred, truth, valid=valid, known=known)
    pos = dti_binary(pred, truth, active=valid & ~known)
    for key in ("tp", "fp", "fn", "dti"):
        assert kw[key] == pytest.approx(pos[key], rel=0, abs=1e-12)
    with pytest.raises(TypeError):
        dti_binary(pred, truth, valid, valid=valid)


def test_leakage_canary_detects_a_leak(fixture):
    """A feature that IS the truth must score AUC 1.0 — the canary has to fire."""
    cat = fixture["catalogue"]
    auc = promoted.leakage_canary(cat.astype(float), cat, fixture["footprint"])
    assert auc == pytest.approx(1.0)
    rng = np.random.default_rng(1)
    noise = rng.random(cat.shape)
    assert promoted.leakage_canary(noise, cat, fixture["footprint"]) == pytest.approx(
        0.5, abs=0.06)
