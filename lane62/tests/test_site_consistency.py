"""The site must not disagree with the evidence.

This module exists because a real bug of exactly this class was found in Pass 3:
`docs/index.html` printed a superseded overlap figure (0.9416, from an older
`evidence/uniqueness.json`) while the receipts and every other page printed the
gate's discriminating-leg figure (0.4066).  A number that appears on the page a
reviewer reads first must be the same number the receipt carries.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EV = ROOT / "evidence"

PAGES = ["index", "executive-summary", "results", "profiles", "research",
         "sources", "irregularities", "run-card"]


def load(p: Path):
    return json.loads(p.read_text())


@pytest.fixture(scope="module")
def site():
    return load(DOCS / "data" / "site.json")


@pytest.fixture(scope="module")
def gate():
    return load(EV / "uniqueness_gate.json")


def text_of(page: str) -> str:
    s = (DOCS / f"{page}.html").read_text()
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s)


def money(x: float, nd: int = 6) -> str:
    return f"{x:.{nd}f}"


def test_every_page_exists_and_carries_the_nav():
    for page in PAGES:
        p = DOCS / f"{page}.html"
        assert p.exists(), page
        body = p.read_text()
        assert len(body) > 1500, page
        for other in PAGES:
            assert f'href="{other}.html"' in body, (page, other)


def test_index_prints_the_strict_gate_and_keeps_diagnostics_separate(site, gate):
    g = gate[site["files"]["primary"]["name"]]
    t = text_of("index").upper()
    strict = money(g["max_overlap_all"], 4)
    diagnostic = money(g["worst_overlap_discriminating"]["overlap_3px_one_sided"], 4)
    assert g["verdict"] == "DUPLICATE - STOP"
    assert "DUPLICATE" in t and "DO NOT SUBMIT" in t
    assert strict in t and diagnostic in t
    assert "JACCARD" in t and "DIAGNOSTIC" in t
    assert "DOES NOT" in t or "DO NOT" in t


def _number_printed(t: str, value: float, nds=(4, 6)) -> str:
    """Return the formatting of `value` that the page actually used."""
    for nd in nds:
        if f"{value:.{nd}f}" in t:
            return f"{value:.{nd}f}"
    assert repr(value)[:10] in t, value
    return repr(value)


def test_holdout_numbers_are_consistent_and_not_promoted_on_the_landing_page(site):
    pa = site["files"]["primary"]["stats"]
    a = pa["instrumentA"]["dti"]
    b = pa["instrumentB"]["dti"]
    for page in ("results", "executive-summary", "run-card"):
        t = text_of(page)
        _number_printed(t, a)
        _number_printed(t, b)
        assert "HOLDOUT-DTI" in t
        assert f"{pa['n_dots']:,}" in t, (page, pa["n_dots"])
    # The landing page should prioritize the stop verdict, not promote proxy scores.
    index = text_of("index")
    assert "DUPLICATE" in index and "DO NOT SUBMIT" in index
    # B' is a mass-matched proxy diagnostic, reported where the economics are discussed.
    for page in ("results", "run-card", "research"):
        _number_printed(text_of(page), pa["instrumentB_prime_dti"])
    assert pa["credit_bar_at_s_0p2778"] < pa["mean_credit_per_dot"] * 2


def test_secondary_is_described_as_a_duplicate_wherever_it_is_linked(gate, site):
    s = gate[site["files"]["secondary"]["name"]]
    assert s["verdict"] == "DUPLICATE - STOP"
    for page in ("index", "run-card", "results"):
        t = text_of(page)
        if site["files"]["secondary"]["name"] in (DOCS / f"{page}.html").read_text():
            assert "DUPLICATE" in t.upper()
            assert "DO NOT SUBMIT" in t.upper()


def test_primary_receipt_matches_the_shipped_bytes(site):
    name = site["files"]["primary"]["name"]
    tif = DOCS / "downloads" / name
    rec = load(DOCS / "downloads" / name.replace(".tif", ".json"))
    assert tif.stat().st_size == rec["bytes"]
    assert hashlib.sha256(tif.read_bytes()).hexdigest() == rec["sha256"]
    assert rec["n_non_finite"] == 0
    assert rec["n_positive_inside_footprint"] > 0
    assert rec["min_inside"] >= 0.0 and rec["max_inside"] <= 1.0
    assert rec["meta"]["nodata"] is None
    assert all(c["ok"] for c in rec["checks"])
    assert rec["portal_error_cannot_occur"] is True
    assert rec["dots_on_catalogue"]["n_positive_on_catalogue"] == 0


def test_readme_quotes_the_primary_hash_and_the_honest_verdict():
    r = (ROOT / "README.md").read_text()
    rec = load(DOCS / "downloads" / "gems62-lahontan-datum-break-dotted-primary-zeros.json")
    assert rec["sha256"][:16] in r
    assert "NOT RECOMMENDED" in r or "negative" in r.lower()
    assert "DO NOT SUBMIT" in r
    assert "MUST GENERATE A UNIQUE TIF SUBMISSION" in r          # standing brief, verbatim


def test_run_card_has_every_field_the_protocol_requires():
    rc = load(DOCS / "data" / "run_card.json")
    for key in ("hypothesis", "mechanism", "non_fault_process_that_could_mimic_it",
                "holdout_dti", "correlation_and_overlap_vs_registry", "raster_sha256",
                "validator_output", "submission_name", "note_140", "verdict",
                "deliverable_1"):
        assert key in rc, key
    assert len(rc["note_140"]) <= 140, len(rc["note_140"])
    assert rc["verdict"] == "negative"
    rec = load(DOCS / "downloads" / "gems62-lahontan-datum-break-dotted-primary-zeros.json")
    assert rc["raster_sha256"] == rec["sha256"], "run card hash must be the shipped hash"
    ci = rc["holdout_dti"]["instrumentA"]["ci95"]
    assert ci[0] <= rc["holdout_dti"]["instrumentA"]["value"] <= ci[1], "CI must bracket"
    assert rc["holdout_dti"]["instrumentB"]["edge"] > 0
    registry = rc["correlation_and_overlap_vs_registry"]
    assert registry["verdict"] == "DUPLICATE - STOP"
    assert registry["strict_gate_pass"] is False
    assert registry["overlap_trip"] is True
    assert registry["jaccard_is_gate"] is False
    assert registry["preplacement_surface_gate"].startswith("NOT VERIFIED")
    # the second artefact is documented as not-submittable in the same card
    sec = rc["second_artifact"]
    assert sec["status"].upper() == "DO NOT SUBMIT"
    assert "0.9885" in sec["reason"] and "sparse comparator" in sec["reason"]
    assert sec["sha256"] == load(
        DOCS / "downloads" / sec["name"].replace(".tif", ".json"))["sha256"]


def test_out_of_footprint_cells_are_zero_and_footprint_is_not_blank(site):
    import numpy as np
    from gems62 import grid as G

    rec = load(DOCS / "downloads" /
               site["files"]["primary"]["name"].replace(".tif", ".json"))
    assert rec["checks"][8]["check"] == "zero_outside_footprint"
    assert rec["checks"][8]["ok"] is True
    # the shipped dot count equals the receipt's, i.e. the file was not re-saved
    assert rec["n_positive_inside_footprint"] == site["files"]["primary"]["stats"]["n_dots"]


def test_sibling_lane_crosscheck_is_distinct_and_reported():
    x = load(EV / "crosscheck_sibling_lane.json")
    assert x["pairs"], "the sibling-lane comparison must have run"
    for row in x["pairs"]:
        assert row["duplicate_under_protocol"] is False, row
        assert row["overlap_3px_one_sided"] <= 0.70, row
        assert abs(row["spearman"]) <= 0.90, row
    t = text_of("index")
    assert "sibling-lane cross-check" in t.lower()
    assert f"{x['pairs'][0]['overlap_3px_one_sided']:.4f}" in t


def test_no_page_promises_a_score_it_does_not_have():
    for page in PAGES:
        t = text_of(page)
        low = t.lower()
        assert "has an organizer-confirmed score" not in low
        assert "organizer-confirmed score of" not in low
        assert "scored 0." not in low
        if "0.3195" in t:                                  # the stale bar (IR-62-06)
            i = t.index("0.3195")
            assert "stale" in t[max(0, i - 200):i + 200].lower()
    assert "unscored" in text_of("run-card").lower()
    assert "do not submit" in text_of("index").lower()
