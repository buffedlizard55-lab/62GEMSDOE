"""H63M regression tests — the invariants that must hold for the shipped artifact.

They read only the committed evidence JSONs and the shipped raster bytes, so they run
anywhere without the heavy inputs.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest

HERE = pathlib.Path(__file__).resolve().parents[1]
EV = HERE / "evidence"
TIF = (HERE / "lane62-h63" / "docs" / "downloads"
       / "gems62-h63m-multiline-corroborated-90000-zeros.tif")


def _load(name):
    return json.loads((EV / name).read_text())


def test_submission_raster_is_legal():
    if not TIF.exists():
        pytest.skip("shipped raster not present")
    import rasterio
    with rasterio.open(TIF) as s:
        assert s.count == 1
        assert s.dtypes[0] == "float32"
        assert str(s.crs) == "EPSG:32611"
        assert (s.height, s.width) == (3730, 3292)
        assert tuple(round(v, 6) for v in s.transform[:6]) == (
            100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
        a = s.read(1)
        assert s.nodata is None, "a nodata tag is one cause of 'values must be in [0, 1]'"
    assert np.isfinite(a).all()
    assert a.min() >= 0.0 and a.max() <= 1.0


def test_format_receipt_is_self_consistent():
    fin = _load("h63_final.json")
    rec = fin["format_receipt"]
    assert rec["legal"] is True
    assert rec["n_outside_0_1"] == 0
    assert rec["all_finite"] is True
    assert rec["nodata"] is None
    assert fin["validator"]["passed"] is True


def test_random_control_closed_form():
    """c_random = (pi R^2 / 3) * K / A, verified to 15 % on both truth sets."""
    cal = _load("h63_calibration.json")
    for key in ("proxy_off", "catalogue"):
        pred = cal["random_control"][key]["closed_form"]
        meas = cal["random_control"][key]["measured"]
        assert meas > 0
        assert abs(pred - meas) / meas < 0.15, (key, pred, meas)


def test_shipped_artifact_beats_chance_on_the_proxy_instrument():
    fin = _load("h63_final.json")
    pol = _load("h63_policy.json")
    cm = fin["measured"]["proxy_off"]["credit_per_mass"]
    ctrl = pol["random_control_cm"]["90000"]
    assert cm > ctrl, (cm, ctrl)
    assert cm / ctrl > 1.5, f"lift only {cm/ctrl:.2f}x"


def test_supervised_arm_has_no_spatial_skill():
    """The headline negative: AUC ~ 0.5 on held-out spatial blocks."""
    hold = _load("h63a_emission.json")
    for f in hold["auc_per_fold"]:
        assert f["auc_catalogue"] < 0.65, f


def test_lane_returns_a_negative_result():
    lane = _load("h63_lane.json")
    assert lane["n_benches"] > 100
    assert lane["n_flagged_steps"] == 0
    # the reason, in metres: the isobase scatter dwarfs the method resolution
    assert lane["isobase"]["residual_sigma_m"] > 3.0 * lane["constants"]["ELEVATION_RESOLUTION_M"]


def test_uniqueness_gate_is_unsatisfiable_only_for_dense_rasters():
    uctl = _load("h63_uniqueness_control.json")
    for r in uctl["rows"]:
        if not r["test_satisfiable"]:
            assert r["random_frac_within_3px"] > 0.70
            assert r["density_frac"] > 0.03, "unsatisfiability should track density"
        else:
            assert r["mine_frac_within_3px"] < 0.70


def test_run_card_has_every_required_field():
    card = _load("h63_run_card.json")
    for k in ("hypothesis", "mechanism",
              "named_non_fault_process_that_could_mimic_it", "holdout_dti",
              "correlation_vs_registry", "raster", "validator", "submission_note",
              "verdict"):
        assert k in card, k
    assert len(card["submission_note"]) <= 140
    assert card["validator"]["passed"] is True
    assert card["verdict"] in ("promote", "negative")
