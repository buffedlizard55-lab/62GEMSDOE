"""The pre-placement gate must fail closed on empty or partially failing checks."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "lane_check_surface", ROOT / "scripts" / "lane_check_surface.py")
assert SPEC and SPEC.loader
surface = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(surface)


def test_surface_aggregation_requires_both_variants_to_pass():
    passing = {"n_registry": 2, "passed": True}
    failing = {"n_registry": 2, "passed": False}
    assert surface.aggregate_surface_verdict({"full": passing, "evidence": passing}) == {
        "passed": True, "verdict": "DISTINCT LANE"}
    assert surface.aggregate_surface_verdict({"full": passing, "evidence": failing}) == {
        "passed": False, "verdict": "DUPLICATE - STOP"}


def test_empty_surface_registry_is_unverified_not_distinct():
    empty = {"n_registry": 0, "passed": False,
             "verdict": "NOT VERIFIED - EMPTY REGISTRY"}
    assert surface.aggregate_surface_verdict({"full": empty, "evidence": empty}) == {
        "passed": False, "verdict": "NOT VERIFIED - EMPTY REGISTRY"}
    assert surface.aggregate_surface_verdict({}) == {
        "passed": False, "verdict": "NOT VERIFIED - EMPTY REGISTRY"}
