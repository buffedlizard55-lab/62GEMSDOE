#!/usr/bin/env python3
"""Does the *population* of catalogue-absent faults reward any particular placement?

The in-repo holdout instrument is the masked catalogue, i.e. faults that ARE in the
USGS/INGENIOUS product.  The scored truth is the opposite population: faults that are NOT in
it (competition page 967: "newly identified faults in the GeoDAWN region that are not included
in the existing USGS fault database").  The only catalogue-absent fault population available
offline is the USGS State Geologic Map Compilation (SGMC) for Nevada, already fetched as
`build/ext/{sgmc,derived_sgmc}_faults_100m.tif`.

This script measures, for that population:
  * how much of it the catalogue omits, and how far from the catalogue it sits (the flank
    question: are catalogue-absent faults adjacent to mapped traces or spread across basins?);
  * the 300 m coverage delivered by every shipped field and by two controls
    (uniform scatter; catalogue-flank ribbon), plus the *geometric ceiling* of the metric -
    the population's own pixels subsampled at 300 m, which is what a perfect detector would
    emit;
  * the official distance-weighted Tversky index with the SGMC-absent population standing in
    for the hidden truth -- labelled OFF-CATALOGUE-PROXY everywhere, never a score.

Usage:  python3 scripts/offcatalogue_coverage.py [--out evidence/offcatalogue_coverage.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

import numpy as np
import rasterio
from scipy import ndimage

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

R = 300.0          # the official kernel radius, metres
PX = 100.0         # cell size, metres
ALPHA, BETA = 0.2, 0.8


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def inside(mask: np.ndarray) -> np.ndarray:
    """Pixels of `mask` that are not on the outer 1-cell frame (so a 300 m EDT is exact)."""
    out = np.zeros_like(mask)
    out[1:-1, 1:-1] = mask[1:-1, 1:-1]
    return out


def edt_to(mask: np.ndarray, spacing: int = 5) -> np.ndarray:
    """Distance (metres) to the nearest True cell of `mask`, EDT over the whole raster."""
    if not mask.any():
        return np.full(mask.shape, np.inf, dtype=np.float64)
    d = ndimage.distance_transform_edt(~mask, sampling=(PX, PX))
    return d


def dti(pred: np.ndarray, truth: np.ndarray) -> dict:
    """Official distance-weighted Tversky index, alpha 0.2 / beta 0.8, R = 300 m.

    k(d) = max(1 - d/R, 0).  TP_w = sum over truth of max over predictions of p*k;
    FP_w = sum over predicted > 0 of p*(1 - max_g k); FN_w = sum over truth of 1 - max_d p*k.
    """
    t = inside(truth)
    if not t.any():
        return {}
    d_pt = edt_to(inside(pred))                       # truth -> predictions
    k_t = np.clip(1.0 - d_pt[t] / R, 0.0, None)       # best k for each truth pixel
    tp = float(k_t.sum())
    fn = float((1.0 - k_t).sum())
    if pred.any():
        d_tp = edt_to(t)                               # predictions -> truth
        k_p = np.clip(1.0 - d_tp[pred] / R, 0.0, None)
        fp = float((1.0 - k_p).sum())
    else:
        fp = 0.0
    denom = tp + ALPHA * fp + BETA * fn
    return {"TP_w": tp, "FP_w": fp, "FN_w": fn,
            "DTI": (tp / denom) if denom else 0.0,
            "coverage_frac": float((k_t > 0).mean()),
            "mean_k_on_covered": float(k_t[k_t > 0].mean()) if (k_t > 0).any() else 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="evidence/offcatalogue_coverage.json")
    ap.add_argument("--ext", default="build/ext")
    ap.add_argument("--seed", type=int, default=20261012)
    args = ap.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]

    with rasterio.open(root / "data" / "labels.tif") as s:
        lab = s.read(1)
    with rasterio.open(root / "data" / "sample_submission.tif") as s:
        fp_mask = np.isfinite(s.read(1))
    cat = lab == 1
    region = fp_mask
    with rasterio.open(root / args.ext / "derived_sgmc_faults_100m.tif") as s:
        sgmc = s.read(1).astype(bool)
    with rasterio.open(root / args.ext / "sgmc_faults_100m.tif") as s:
        sgmc_raw = s.read(1).astype(bool)

    report: dict = {
        "generated_by": "scripts/offcatalogue_coverage.py",
        "labelling": "OFF-CATALOGUE-PROXY: the truth stand-in is USGS SGMC Nevada faults that the "
                     "competition catalogue omits.  It is a different population from the hidden "
                     "expert-labelled truth.  No number here is a score.",
        "geometry": {
            "grid_px": int(lab.size),
            "catalogue_px": int(cat.sum()),
            "scored_region_px": int(region.sum()),
            "scored_region_km2": round(float(region.sum()) * 0.01, 1),
            "sgmc_px_raw": int(sgmc_raw.sum()),
            "sgmc_px_derived": int(sgmc.sum()),
            "sgmc_outside_scored_region": int((sgmc & ~region).sum()),
        },
        "inputs": {p: sha256(root / p) for p in
                   ("data/labels.tif", "data/sample_submission.tif",
                    f"{args.ext}/derived_sgmc_faults_100m.tif")},
        "populations": {},
    }

    d_cat = edt_to(inside(cat))
    for r in (0, 200, 300, 400, 1000, 2000):
        sel = sgmc & region & (d_cat > r)
        report["populations"][f"sgmc_absent_and_farther_than_{r}m"] = {
            "n_px": int(sel.sum()),
            "frac_of_sgmc_in_region": round(float(sel.sum() / max((sgmc & region).sum(), 1)), 4),
        }

    hist = sgmc & region
    dd = d_cat[hist]
    edges = [0, 100, 200, 300, 400, 600, 800, 1000, 1500, 2000, 3000, 5000, 10000]
    report["distance_to_catalogue_of_sgmc_faults_m"] = {
        f"{edges[i]}-{edges[i + 1]}":
            {"n": int(((dd >= edges[i]) & (dd < edges[i + 1])).sum()),
             "frac": round(float(((dd >= edges[i]) & (dd < edges[i + 1])).mean()), 4)}
        for i in range(len(edges) - 1)}
    report["distance_to_catalogue_of_sgmc_faults_m"]["summary"] = {
        "median_m": float(np.median(dd)), "mean_m": float(dd.mean()),
        "frac_within_300m": round(float((dd <= 300).mean()), 4),
        "frac_within_1000m": round(float((dd <= 1000).mean()), 4)}

    # the uniform background rate: what fraction of scored *pixels* are within 300 m of truth
    truth = sgmc & region & (d_cat > 300)
    bg = edt_to(inside(truth))
    report["background_frac_scored_pixels_within_300m_of_population"] = \
        round(float((bg[region] <= R).mean()), 4)

    # ---- controls and shipped fields ------------------------------------------------
    fields = {
        "uniform_scatter_40k_min300m": None,       # built below
        "champion_h33_2_b2": pathlib.Path("/tmp/registry/GEMSDOE32__gemsdoe32-h33-h33-2-b2-"
                                          "20261004T220000Z-e5eb6e7e-zeros.tif"),
        "h27_4_solo_d28": pathlib.Path("/tmp/registry/GEMSDOE28__gems28-h27-4-r1-solo-d2-8-"
                                       "20261003-8acb75e1f2cc-allfinite.tif"),
        "d28_poisson300m_44090": pathlib.Path("/tmp/registry/GEMSDOE30__gemsdoe30-d28-poisson300m-"
                                              "offcat-44090-20261003T233156Z-91eae1ca-nanoutside.tif"),
        "sgmc_hedge_d10_85k": pathlib.Path("/tmp/registry/GEMSDOE30__gemsdoe30-sgmc-hedge-d10-85k-"
                                           "20261003-ac08b41e-zeros.tif"),
        "h63_diffuse_isolated_40k": root / "build/h63/"
                                          "gems62-h63-diffuse-isolated-offcat-40k-zeros.tif",
    }
    # uniform scatter with the same hard-core rule as the H63 builder: 40k dots on a 3-px
    # hex lattice, random draw, all inside the scored region.
    rng = np.random.default_rng(args.seed)
    cand = np.zeros_like(cat)
    rows = np.arange(1, cat.shape[0] - 1, 1)
    for y in rows:
        cand[y, 1 + (y % 3 < 2)::3] = True
    cand &= region
    idx = np.flatnonzero(cand.ravel())
    pick = rng.choice(idx, size=min(40_000, idx.size), replace=False)
    uni = np.zeros_like(cat)
    uni.ravel()[pick] = True

    results = {}
    for name, path in fields.items():
        if path is None:
            pred = uni
            src = "uniform draw over the scored region, hex rows every 3 px, seed %d" % args.seed
        else:
            with rasterio.open(path if path.is_absolute() else root / path) as s:
                pred = s.read(1) > 0
            src = str(path)
        res = dti(pred, truth)
        res.update({
            "mass": int(pred.sum()),
            "frac_dots_in_scored_region": round(float((pred & region).sum() / max(pred.sum(), 1)), 4),
            "source": src,
            **{f"coverage_of_population_within_{R:.0f}m": res.get("coverage_frac")},
            "enrichment_vs_background": round(float(res["coverage_frac"]) /
                                              report["background_frac_scored_pixels_within_300m_of_population"], 3)
            if "coverage_frac" in res else None,
        })
        results[name] = res

    # geometric ceiling: the population's own pixels, subsampled on the 3-px hex lattice
    ceil_mask = truth & cand
    res = dti(ceil_mask, truth)
    res.update({"mass": int(ceil_mask.sum()), "source": "truth pixels subsampled on the 3-px hex lattice",
                "frac_dots_in_scored_region": 1.0,
                "enrichment_vs_background": round(float(res["coverage_frac"]) /
                                                  report["background_frac_scored_pixels_within_300m_of_population"], 3)})
    results["ceiling_truth_subsampled_3px"] = res
    report["fields"] = results
    report["metric_identity"] = ("TP_w + FN_w = |G| identically, so "
                                 "DTI = TP_w / (0.2*M + 0.8*|G| + 0.2*(TP_w - M_cov)) "
                                 "with M the predicted mass and M_cov the predicted pixels that "
                                 "sit within R of any truth pixel; hence DTI <= TP_w/(0.2*M + 0.8*|G|).")

    out = root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
