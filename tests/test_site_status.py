"""The published root site must not offer upload steps for a stopped artifact."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v8_run_card_records_both_protocol_halves_honestly():
    card = json.loads((ROOT / "evidence" / "run_card_v8.json").read_text())
    assert card["registry"]["verdict"] == "DUPLICATE - STOP"
    assert card["registry"]["overlap_trip"] is True
    assert card["registry"]["preplacement_surface_gate"].startswith("NOT VERIFIED")
    assert card["holdout"]["evidence_class"].startswith("HOLDOUT-DTI")
    assert card["holdout"]["dti_ci95"] is None


def test_executive_summary_does_not_offer_upload_instructions():
    html = (ROOT / "docs" / "executive-summary.html").read_text().lower()
    assert "do not submit" in html
    assert "duplicate - stop" in html
    assert "press submit" not in html
    assert "scored submission" not in html
    assert "not verified" in html


def test_legacy_site_builder_fails_closed_on_incomplete_strict_receipts():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "make_site.py")],
        cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0
    assert "strict all-comparator" in result.stderr.lower()
