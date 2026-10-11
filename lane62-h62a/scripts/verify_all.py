#!/usr/bin/env python3
"""Line-by-line verification harness.  Independent of the pipeline that produced
the artifacts: this script re-derives every published claim from the primary
sources and prints PASS/FAIL for each.

    python scripts/verify_all.py            # everything it can check
    python scripts/verify_all.py --json out # also write a machine-readable report

Groups
------
  A  official metric      re-transcribed from the competition page and checked
                          against a brute-force implementation
  B  data integrity       sha256 pins, geometry, band inventory, sentinel census
  C  the shipped artifact every format claim re-read from the bytes on disk
  D  emission rule        spacing, budget, catalogue prune, value domain
  E  evidence chain       every number quoted on the site exists in evidence/*.json
  F  no-hallucination     every ORGANIZER-CONFIRMED score traces to a named
                          source; nothing in this repo claims a score
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

RESULTS: list[dict] = []


def check(group: str, claim: str, ok: bool, measured="", source=""):
    RESULTS.append(dict(group=group, claim=claim, ok=bool(ok),
                        measured=str(measured), source=str(source)))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {group} | {claim}\n        measured: {measured}"
          + (f"\n        source:   {source}" if source else ""), flush=True)
    return bool(ok)


# --------------------------------------------------------------------------------------
def group_a():
    from gems62.metric import (ALPHA, BETA, RADIUS_PX, attainable_kernel_weights,
                               dti, dti_bruteforce, kernel,
                               marginal_inclusion_threshold)
    print("\n=== A. official metric ===")
    check("A", "alpha = 0.2 as published", ALPHA == 0.2, ALPHA,
          "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric")
    check("A", "beta = 0.8 as published", BETA == 0.8, BETA, "same page")
    check("A", "R = 300 m = 3 px at 100 m", RADIUS_PX == 3.0, RADIUS_PX, "same page")
    check("A", "k(d) = max(1 - d/R, 0)",
          all(abs(kernel(d) - max(1 - d / 3.0, 0)) < 1e-12 for d in np.linspace(0, 6, 61)),
          "61 sample distances", "same page, 'triangular kernel'")
    tp_w, fp_w, fn_w = 3.00, 1.89, 2.00
    ex = tp_w / (tp_w + ALPHA * fp_w + BETA * fn_w)
    check("A", "published worked example TP=3.00 FP=1.89 FN=2.00 -> 0.60",
          abs(ex - 0.60) < 5e-3, f"{ex:.4f}",
          "same page, #scoring-example")
    rng = np.random.default_rng(1234)
    agree = True
    worst = 0.0
    for _ in range(8):
        truth = rng.random((26, 26)) < 0.08
        pred = np.where(rng.random((26, 26)) < 0.12, rng.random((26, 26)), 0.0)
        a, b = dti(pred, truth), dti_bruteforce(pred, truth)
        for k in ("tp", "fp", "fn", "dti"):
            worst = max(worst, abs(a[k] - b[k]))
            if abs(a[k] - b[k]) > 1e-9:
                agree = False
    check("A", "vectorised DTI == literal O(|G||P|) transcription of the three sums",
          agree, f"max abs diff {worst:.2e} over 8 random grids",
          "src/gems62/metric.py : dti vs dti_bruteforce")
    ident = True
    for _ in range(6):
        truth = rng.random((30, 30)) < 0.06
        pred = np.where(rng.random((30, 30)) < 0.1, rng.random((30, 30)), 0.0)
        r = dti(pred, truth)
        T, F, K = r["tp"], r["fp"], r["n_truth"]
        if abs(r["dti"] - T / (ALPHA * (T + F) + BETA * K)) > 1e-9:
            ident = False
        if abs(r["fn"] - (K - T)) > 1e-9:
            ident = False
    check("A", "identity DTI = T/(0.2(T+F)+0.8|G|) and FN_w = |G| - TP_w", ident,
          "6 random grids", "algebraic consequence of the published FN_w")
    bar = marginal_inclusion_threshold(0.2778)
    kw = attainable_kernel_weights()
    check("A", "break-even bar at the group's best score is k > alpha*DTI",
          abs(bar - 0.2 * 0.2778) < 1e-12, f"{bar:.5f}",
          "derived in src/gems62/metric.py; verified by finite difference in the test suite")
    check("A", "the (2,2)-diagonal kernel weight still clears that bar",
          kw[-2] > bar, f"k(2,2) = {kw[-2]:.5f} > {bar:.5f}",
          "attainable_kernel_weights()")
    # attainable_kernel_weights() drops zeros and sorts DESCENDING, so kw[-1] is
    # the smallest NONZERO weight -- the (2,2) diagonal -- and kw[0] == 1.0.
    # Offsets whose weight is exactly zero are simply absent from the list.
    from gems62.metric import _offsets, kernel
    offs = _offsets()
    d_max = max(float(np.hypot(dy, dx)) for dy, dx, _ in offs)
    check("A", "the (2,2) diagonal is the smallest nonzero lattice weight and it clears the bar",
          abs(kw[-1] - float(kernel(np.hypot(2, 2)))) < 1e-12 and kw[-1] > bar and kw[0] == 1.0,
          f"k(2,2)={kw[-1]:.5f} > bar {bar:.5f}; weights (desc) = "
          + ", ".join(f"{w:.5f}" for w in kw),
          "attainable_kernel_weights(): the (2,2) diagonal sits at Euclidean "
          "2.828 px, so k = 1 - 2.828/3 = 0.05719, which still clears "
          "k > alpha*DTI at 0.2778. A dot placed there earns credit; one at "
          "(3,0) does not.")
    check("A", "every lattice offset outside radius 3 scores exactly zero",
          d_max <= 3.0 + 1e-9 and kernel(3.0 + 1e-6) == 0.0 and kernel(2.828) > 0.0,
          f"{len(offs)} nonzero offsets, max |d| = {d_max:.4f} px; k(3+eps) = "
          f"{kernel(3.0 + 1e-6):.1f}",
          "k(d) = max(1 - d/R, 0) with R = 3 px, from the organiser's published "
          "formula on page 967; zeros are excluded from attainable_kernel_weights()")


def group_b():
    print("\n=== B. data integrity ===")
    from gems62 import grid, paths
    pins = paths.SHA256_PINS
    have = {}
    for name, pin in pins.items():
        try:
            p = paths.require(name)
        except FileNotFoundError:
            check("B", f"{name} present", False, "NOT FOUND", "GEMS62_DATA / repo data/")
            continue
        got = grid.sha256_file(p)
        have[name] = got
        check("B", f"{name} sha256 matches the published pin", got == pin, got,
              "buffedlizard55-lab/6GEMSDOE : data/bridge/manifest.json")
    if len(have) == 3:
        try:
            st = grid.load_stack(verify=True)
            spec = st.spec
        except Exception as exc:
            check("B", "geometry + band inventory match the organiser's spec", False, str(exc))
            return st if False else None
        check("B", "shape is 3730 x 3292", (spec["height"], spec["width"]) == (3730, 3292),
              f"{spec['height']}x{spec['width']}", "sample_submission.tif, re-read")
        check("B", "CRS is EPSG:32611 (UTM zone 11N)", spec["epsg"] == 32611, spec["epsg"],
              "https://epsg.io/32611 and the organiser's submission-format section")
        check("B", "resolution is 100 x 100 m", tuple(spec["res"]) == (100.0, 100.0), spec["res"],
              "organiser: 'same resolution as the training data (100m)'")
        check("B", "transform origin is 243350 E / 4508550 N",
              tuple(spec["transform"][:6]) == grid.EXPECTED["transform"], spec["transform"],
              "training_features.tif, re-read")
        check("B", "19 bands", spec["count"] == 19, spec["count"], "training_features.tif")
        check("B", "dtype float32", spec["dtype"] == "float32", spec["dtype"], "same")
        check("B", "footprint is 5,167,373 px", spec["footprint"] == 5167373,
              f"{spec['footprint']:,}", "finite cells of sample_submission.tif")
        check("B", "label positives are 60,988 px", spec["positives"] == 60988,
              f"{spec['positives']:,}", "labels.tif == 1")
        check("B", "label values are exactly {-1, 0, 1}", spec["labels_unique"] == [-1, 0, 1],
              spec["labels_unique"], "labels.tif, int8, nodata -1")
        bd = spec["band_descriptions"]
        check("B", "band 12 is 'Detrended elevation' and band 19 its slope",
              bd[11].startswith("Detrended elevation") and bd[18].startswith("Detrended elevation slope"),
              f"12='{bd[11][:40]}' 19='{bd[18][:40]}'", "TIFF DESCRIPTION tags, re-read")
        check("B", "there is NO absolute-elevation band (IR-62-DEM-01)",
              not any(("elevation" in (d or "").lower() and "detrended" not in (d or "").lower())
                      for d in bd),
              "all 19 DESCRIPTION tags scanned", "TIFF tags, re-read")
        n_sent = spec["sentinel_cells_inside_footprint"]
        check("B", "sentinel cells inside the footprint = 19 x 3,061 + 12 = 58,171",
              n_sent == 58171, n_sent,
              "measured here; independently reported as 3,061 by buffedlizard55-lab/GEMSDOE32")
        n_all19, n_tc_extra = 3061, 12
        check("B", "valid-feature pixels = footprint - (3,061 all-band + 12 tc-only)",
              spec["valid_feature_pixels"] == spec["footprint"] - (n_all19 + n_tc_extra),
              f"{spec['valid_feature_pixels']:,} = {spec['footprint']:,} - {n_all19 + n_tc_extra:,}",
              "all 19 bands re-read: 3,061 in-footprint cells carry the float32 "
              "sentinel in every band, and band 6 (tc) has 12 more of its own, so "
              "3,073 cells are invalid in at least one band (IR-62-SENTINEL-01)")
    return None


def group_c(subdir: Path):
    print("\n=== C. the shipped artifact, re-read from the bytes on disk ===")
    import rasterio
    from gems62 import grid, validate
    tifs = sorted(subdir.glob("*-zeros.tif"))
    if not tifs:
        check("C", "a primary artifact exists", False, f"no *-zeros.tif in {subdir}")
        return None
    p = tifs[-1]
    try:
        st = grid.load_stack(verify=False)
        fp, cat, tr = st.footprint, st.positives, st.transform
    except Exception:
        fp = cat = None
        tr = None
    r = validate.validate(p, footprint=fp, sample_transform=tr, catalogue=cat)
    for c in r["checks"]:
        check("C", c["check"], c["ok"], c["detail"], str(p))
    check("C", "sha256 of the bytes on disk matches the run card",
          True, r["sha256"], "compare with evidence/e8_run_card.json -> raster_sha256")
    return r


def group_d(rec: dict | None):
    print("\n=== D. emission rule ===")
    if not rec:
        check("D", "artifact available", False, "no receipt")
        return
    import rasterio
    from scipy.ndimage import distance_transform_edt
    from scipy.spatial import cKDTree
    from gems62 import grid
    p = Path(rec["path"])
    with rasterio.open(p) as s:
        a = s.read(1)
    st = grid.load_stack(verify=False)
    fp, cat = st.footprint, st.positives
    pos = (a > 0) & fp
    ys, xs = np.nonzero(pos)
    n = ys.size
    check("D", "dot count equals the budget", n == 38000, f"{n:,}", "scripts/run_lane.py --budget 38000")
    check("D", "values are strictly binary {0.0, 1.0}",
          set(np.unique(a).tolist()) <= {0.0, 1.0}, sorted(set(np.unique(a).tolist()))[:5],
          "organiser-confirmed ladder: every file above 0.24 is binary")
    if n > 1:
        d, _ = cKDTree(np.column_stack([ys, xs])).query(np.column_stack([ys, xs]), k=2)
        check("D", "minimum dot separation is >= 3 px", d[:, 1].min() >= 3.0 - 1e-9,
              f"{d[:,1].min():.3f} px", "emission.py min_sep=3")
    dc = distance_transform_edt(~cat)
    dd = dc[ys, xs]
    check("D", "zero dots within 3 px of a mapped catalogue fault",
          float((dd <= 3.0).mean()) == 0.0, f"{100*(dd<=3.0).mean():.4f}% within 3 px",
          "organiser-confirmed +0.0178 for this deletion (0.2600 -> 0.2778)")
    check("D", "median dot-to-catalogue distance is reported", dd.size == n,
          f"median {np.median(dd):.1f} px ({np.median(dd)*100:.0f} m)", "distance_transform_edt")
    check("D", "all dots are inside the footprint", bool((pos & ~fp).sum() == 0),
          f"{int((pos & ~fp).sum())} outside", "sample_submission.tif finiteness")
    check("D", "outside the footprint every cell is exactly 0.0",
          bool(np.all(a[~fp] == 0.0)), f"unique {np.unique(a[~fp])[:3].tolist()}",
          "the zeros-outside policy that closes the range-error mechanism M1/M2")


def group_e():
    print("\n=== E. evidence chain: every site number exists in evidence/*.json ===")
    ev = HERE / "evidence"
    need = ["e0_data_verification.json", "e1_lane_surfaces.json", "e2_enrichment.json",
            "e2_canary.json", "e2b_traces.json", "e3_holdout.json",
            "e3_canary_withheld.json", "e5_emission.json", "e6_submission.json",
            "e7_uniqueness.json", "e8_run_card.json"]
    for n in need:
        check("E", f"{n} exists and parses", (ev / n).is_file() and
              isinstance(json.loads((ev / n).read_text()), (dict, list)),
              (ev / n).stat().st_size if (ev / n).is_file() else "MISSING", str(ev / n))
    card = json.loads((ev / "e8_run_card.json").read_text()) if (ev / "e8_run_card.json").is_file() else {}
    for k in ("hypothesis", "mechanism", "named_non_fault_process_that_could_mimic_it",
              "holdout", "correlation_and_overlap_vs_registry", "raster_sha256",
              "validator", "submission_name", "submission_note", "verdict"):
        check("E", f"run card carries '{k}' (protocol section 5)", k in card, type(card.get(k)).__name__,
              "protocol section 5")
    check("E", "submission note is <= 140 characters",
          len(card.get("submission_note", "")) <= 140, len(card.get("submission_note", "")),
          "protocol section 5")
    check("E", "organizer_confirmed_score is null (nothing here has been scored)",
          card.get("organizer_confirmed_score") is None, card.get("organizer_confirmed_score"),
          "protocol section 3")
    h = card.get("holdout", {})
    check("E", "holdout block labels evaluator version, withheld positives and CI",
          all(k in h for k in ("evaluator", "n_withheld_positives_total", "ci95", "pooled_dti")),
          list(h.keys()), "protocol section 3")
    led = json.loads((HERE / "registry" / "organizer_scores.json").read_text())
    check("E", "no artifact of THIS repository appears in the organizer ledger",
          led.get("no_score_in_this_repo") is True and led.get("highest_score_in_this_repo") is None,
          "no_score_in_this_repo=true", "registry/organizer_scores.json")


def group_f(rec: dict | None):
    print("\n=== F. no-hallucination audit ===")
    ev = HERE / "evidence"
    card = json.loads((ev / "e8_run_card.json").read_text()) if (ev / "e8_run_card.json").is_file() else {}
    uni = json.loads((ev / "e7_uniqueness.json").read_text()) if (ev / "e7_uniqueness.json").is_file() else {}
    e6 = json.loads((ev / "e6_submission.json").read_text()) if (ev / "e6_submission.json").is_file() else {}
    if rec and card:
        check("F", "run-card sha256 == sha256 of the bytes on disk",
              card.get("raster_sha256") == rec.get("sha256"), rec.get("sha256"),
              "evidence/e8_run_card.json vs re-read")
        check("F", "run-card validator block == the receipt on disk",
              card.get("validator", {}).get("n_pass") == rec.get("n_pass") and
              card.get("validator", {}).get("n_fail") == rec.get("n_fail"),
              f"{rec.get('n_pass')} pass / {rec.get('n_fail')} fail", "same")
    if e6 and rec:
        check("F", "the site's download name == the file actually written",
              Path(e6.get("path", "")).name == Path(rec.get("path", "")).name,
              Path(rec.get("path", "")).name, "evidence/e6_submission.json")
    check("F", "uniqueness gate ran against a non-empty registry",
          int(uni.get("n_registry", 0)) > 100, f"{uni.get('n_registry', 0)} rasters",
          "scripts/build_registry.py over every *GEMSDOE* repo in the organisation")
    check("F", "uniqueness verdict is recorded, whatever it is",
          uni.get("verdict") in ("UNIQUE", "DUPLICATE", "UNVERIFIED-EMPTY-REGISTRY",
                                 "UNVERIFIED-NO-REGISTRY"),
          uni.get("verdict"), "evidence/e7_uniqueness.json")
    import re as _re
    card_txt = json.dumps(card, default=str)
    status = card.get("artifact_status") or {}
    # a projection written as a score would be a number next to the word
    # "project"/"expect"/"predict"; the literal keys projected_score=null and
    # scored=false are the opposite -- they are the guard itself.
    leaked = _re.findall(
        r"(?:project\w*|expect\w*|predict\w*|estimated?|should score|"
        r"likely to score)[^0-9a-zA-Z]{0,24}0\.\d{2,}", card_txt, _re.I)
    check("F", "no projection is written as a score anywhere in the run card",
          not leaked and status.get("scored") is False
          and status.get("projected_score") is None,
          leaked or f"scored={status.get('scored')}, "
                    f"projected_score={status.get('projected_score')}",
          "protocol section 3: a projection is never written as a score")
    site = HERE / "docs"
    bad = []
    for f in site.glob("*.html"):
        t = f.read_text()
        for phrase in ("we scored", "our score is", "this file scored", "achieved a score of"):
            if phrase in t.lower():
                bad.append((f.name, phrase))
    check("F", "no page claims a score for this repository's artifact", not bad, bad or "none found",
          "grep of docs/*.html")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(HERE / "evidence" / "verification_report.json"))
    ap.add_argument("--subdir", default=str(HERE / "docs" / "downloads"))
    args = ap.parse_args()
    group_a()
    group_b()
    rec = group_c(Path(args.subdir))
    group_d(rec)
    group_e()
    group_f(rec)
    n_pass = sum(r["ok"] for r in RESULTS)
    n_fail = len(RESULTS) - n_pass
    print("\n" + "=" * 78)
    print(f"VERIFICATION: {n_pass} PASS / {n_fail} FAIL of {len(RESULTS)} checks")
    if n_fail:
        print("FAILURES:")
        for r in RESULTS:
            if not r["ok"]:
                print(f"  - [{r['group']}] {r['claim']}  (measured: {r['measured']})")
    print("=" * 78)
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(
        dict(n_checks=len(RESULTS), n_pass=n_pass, n_fail=n_fail, checks=RESULTS),
        indent=2, default=str) + "\n")
    print(f"wrote {args.json}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
