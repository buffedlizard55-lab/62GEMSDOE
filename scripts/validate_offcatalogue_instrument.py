#!/usr/bin/env python3
"""Validate the catalogue-absent-population instrument on the 42 rows that have organiser scores.

`offcatalogue_coverage.py` computes a proxy DTI whose truth stand-in is the USGS SGMC Nevada
fault population that the competition catalogue omits -- i.e. the *same kind of population* the
score actually targets ("faults not included in the existing USGS fault database").  The repo's
previous instrument (credit against the masked catalogue) was inverted (Spearman -0.615) and is
forbidden as a promotion gate (IR-62-11C-04).  Before this instrument may be used for anything,
it has to rank the fields that already have a real score.

This script recomputes the same quantities for every raster in research/proxy_dti_regression.json
whose bytes are present in the local registry cache, and reports the rank correlations.

Usage: python3 scripts/validate_offcatalogue_instrument.py [--cache /tmp/registry]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
import rasterio

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from offcatalogue_coverage import dti, edt_to, inside  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))


def spearman(a, b) -> float:
    ra = np.argsort(np.argsort(np.asarray(a, float)))
    rb = np.argsort(np.argsort(np.asarray(b, float)))
    return float(np.corrcoef(ra, rb)[0, 1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="/tmp/registry")
    ap.add_argument("--out", default="research/offcatalogue_instrument_validation.json")
    args = ap.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    cache = pathlib.Path(args.cache)

    with rasterio.open(root / "data" / "labels.tif") as s:
        lab = s.read(1)
    with rasterio.open(root / "data" / "sample_submission.tif") as s:
        region = np.isfinite(s.read(1))
    cat = lab == 1
    with rasterio.open(root / "build" / "ext" / "derived_sgmc_faults_100m.tif") as s:
        sgmc = s.read(1).astype(bool)
    d_cat = edt_to(inside(cat))
    truth = sgmc & region & (d_cat > 300)

    rows = json.loads((root / "research" / "proxy_dti_regression.json").read_text())
    seen, out = set(), []
    for r in rows:
        base = r["file"]
        if base in seen:
            continue
        seen.add(base)
        path = cache / base
        if not path.exists():
            continue
        try:
            with rasterio.open(path) as s:
                arr = s.read(1)
        except Exception:
            continue
        pred = np.isfinite(arr) & (arr > 0)
        if pred.shape != cat.shape:
            continue
        res = dti(pred, truth)
        if not res:
            continue
        rec = {
            "file": base, "repo": r["repo"], "reported_score": r["reported_score"],
            "mass": int(pred.sum()),
            "frac_on_catalogue": round(float((pred & cat).sum() / max(pred.sum(), 1)), 4),
            "offcat_coverage": round(res["coverage_frac"], 4),
            "offcat_mean_k": round(res["mean_k_on_covered"], 4),
            "offcat_proxy_dti": round(res["DTI"], 4),
            "offcat_tp_w": round(res["TP_w"], 1),
            "offcat_fp_w": round(res["FP_w"], 1),
            "credit_per_dot": round(res["TP_w"] / max(int(pred.sum()), 1), 5),
        }
        out.append(rec)

    scores = [r["reported_score"] for r in out]
    report = {
        "generated_by": "scripts/validate_offcatalogue_instrument.py",
        "population": {"n_truth_px": int(truth.sum()), "def": "USGS SGMC Nevada faults in the "
                       "scored region and farther than 300 m from the competition catalogue"},
        "n_rows": len(out),
        "correlations_with_reported_score": {
            "offcat_proxy_dti": round(spearman([r["offcat_proxy_dti"] for r in out], scores), 4),
            "offcat_coverage": round(spearman([r["offcat_coverage"] for r in out], scores), 4),
            "credit_per_dot": round(spearman([r["credit_per_dot"] for r in out], scores), 4),
            "mass": round(spearman([r["mass"] for r in out], scores), 4),
            "frac_on_catalogue": round(spearman([r["frac_on_catalogue"] for r in out], scores), 4),
        },
        "rows": sorted(out, key=lambda r: -r["reported_score"]),
    }
    rep = root / args.out
    rep.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report["correlations_with_reported_score"], indent=1))
    print(f"n = {len(out)} rows -> {rep}")
    for r in report["rows"][:14]:
        print(f"{r['reported_score']:7.4f} cov {r['offcat_coverage']:.3f} "
              f"proxDTI {r['offcat_proxy_dti']:.4f} cred/dot {r['credit_per_dot']:.4f} "
              f"oncat {r['frac_on_catalogue']:.3f} M {r['mass']:7,d}  {r['file'][:52]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
