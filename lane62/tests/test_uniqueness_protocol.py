"""Binding uniqueness thresholds shared by the lane62 finalizer and CLI gate."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from uniqueness_gate import one_sided_overlap, protocol_verdict  # noqa: E402


def test_dense_comparator_overlap_is_still_a_duplicate_stop():
    gate = protocol_verdict(0.0, 1.0, n_comparators=508)
    assert gate["overlap_trip"] is True
    assert gate["passed"] is False
    assert gate["verdict"] == "DUPLICATE - STOP"


def test_positive_rank_correlation_trips_but_negative_does_not():
    assert protocol_verdict(0.91, 0.0, n_comparators=1)["rho_trip"] is True
    assert protocol_verdict(-0.99, 0.0, n_comparators=1)["passed"] is True


def test_thresholds_are_strictly_exceeded():
    gate = protocol_verdict(0.90, 0.70, n_comparators=1)
    assert gate["rho_trip"] is False
    assert gate["overlap_trip"] is False
    assert gate["passed"] is True


def test_euclidean_three_pixel_radius_excludes_far_diagonal():
    footprint = np.ones((9, 9), dtype=bool)
    mine = np.zeros_like(footprint); mine[1, 1] = True
    theirs = np.zeros_like(footprint); theirs[4, 4] = True
    assert one_sided_overlap(mine, theirs, footprint) == 0.0
    theirs.fill(False); theirs[1, 4] = True
    assert one_sided_overlap(mine, theirs, footprint) == 1.0


def test_empty_registry_cannot_certify_distinctness():
    gate = protocol_verdict(float("nan"), 0.0, n_comparators=0)
    assert gate["passed"] is False
    assert gate["verdict"] == "NOT VERIFIED - EMPTY REGISTRY"
