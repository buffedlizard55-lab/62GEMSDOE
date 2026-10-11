#!/usr/bin/env python3
"""Rank ORGANIZER-CONFIRMED artifacts against ours on one identical holdout.

The standing constraint is "do not spend a submission slot on an idea that has
not beaten the current holdout best."  Until now the repo had no holdout number
for the 0.2778 file, so that constraint could not be evaluated at all.  This
script closes the gap by scoring FROZEN artifacts -- dot masks read straight
from disk -- through the same segmented hide-and-recover folds as our own arms.

Honesty note carried into the output: a frozen artifact is
INFORMATION-ADVANTAGED relative to the protocol, because it was built with the
full catalogue in hand whereas our arms see only the per-fold visible catalogue.
For the registry files the bias runs AGAINST them: they were built to sit OFF
the mapped catalogue, so avoiding the withheld truth lowers their holdout DTI.
A frozen file that still beats us is therefore beating us on a handicap.

    GEMS62_DATA=... python scripts/compare_holdout.py
    GEMS62_DATA=... python scripts/compare_holdout.py --top 12 --folds 4
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from gems62 import grid, holdout                                       # noqa: E402

REGISTRY = Path.home() / ".cache/gems62/registry/rasters"


def load_mask(path: Path, footprint: np.ndarray) -> np.ndarray | None:
    with rasterio.open(path) as s:
        a = s.read(1).astype(np.float64)
    if a.shape != footprint.shape:
        return None
    return (np.nan_to_num(a, nan=0.0) > 0) & footprint


def find_in_registry(submission: str) -> Path | None:
    """Locate a registry raster whose name contains the submission stem."""
    stem = submission.replace("-zeros", "").replace("-nan", "")
    hits = sorted(p for p in REGISTRY.glob("*.tif") if stem in p.name)
    if not hits:
        return None
    # prefer the -zeros / all-finite twin: it is the form the portal accepted
    for p in hits:
        if p.name.endswith("-zeros.tif"):
            return p
    for p in hits:
        if "allfinite" in p.name or "nan" not in p.name:
            return p
    return hits[0]


def frozen_emission(mask: np.ndarray):
    def _fn(eligible, priority, footprint, visible_catalogue, budget):
        return mask
    return _fn


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10,
                    help="how many organizer-scored artifacts to evaluate")
    ap.add_argument("--folds", type=int, default=4)
    ap.add_argument("--ev", default=str(HERE / "evidence"))
    args = ap.parse_args()

    t0 = time.time()
    stack = grid.load_stack(verify=False)
    fp = stack.footprint
    cat = stack.labels > 0
    print(f"[cmp] stack {time.time()-t0:.0f}s  footprint {int(fp.sum()):,}  "
          f"catalogue {int((cat & fp).sum()):,}", flush=True)

    scores = json.loads((HERE / "registry" / "organizer_scores.json").read_text())["scores"]
    scores = sorted(scores, key=lambda r: -(r.get("score") or 0))

    # ---- ours
    ours = sorted((HERE / "docs" / "downloads").glob("*-zeros.tif"))[-1]
    candidates = [("OURS (H62-A, unscored)", ours, None, None)]

    for rec in scores[: args.top * 3]:
        if len(candidates) > args.top:
            break
        p = find_in_registry(rec["submission"])
        if p is None:
            continue
        if any(p == c[1] for c in candidates):
            continue
        candidates.append((rec["submission"], p, rec["score"], rec.get("dots")))

    print(f"[cmp] {len(candidates)} frozen artifacts to evaluate", flush=True)

    eligible = fp & ~cat                      # same eligibility our arms used
    out = []
    for label, path, org_score, dots in candidates:
        mask = load_mask(Path(path), fp)
        if mask is None:
            print(f"[cmp] SKIP {label}: geometry mismatch", flush=True)
            continue
        n = int(mask.sum())
        if n == 0:
            print(f"[cmp] SKIP {label}: empty", flush=True)
            continue
        rep = holdout.run_holdout(eligible, mask.astype(np.float64), fp, cat,
                                  frozen_emission(mask), n_folds=args.folds,
                                  controls=False, budget=n)
        row = dict(label=label, path=str(path),
                   organizer_confirmed_score=org_score,
                   n_dots=n, dots_declared=dots,
                   holdout_dti=rep.get("pooled_dti"),
                   holdout_dti_ci95=rep.get("fold_dti_ci95"),
                   n_folds=rep.get("n_folds"),
                   withheld_positives=rep.get("withheld_positives_total"),
                   tp=rep.get("pooled_tp"), fp=rep.get("pooled_fp"),
                   fn=rep.get("pooled_fn"),
                   fold_dtis=[f["result"]["dti"] for f in rep.get("folds", [])])
        out.append(row)
        os_ = f"{org_score:.4f}" if isinstance(org_score, float) else "UNSCORED"
        print(f"[cmp] {label[:46]:48s} n={n:>7,} org={os_:>8s} "
              f"HOLDOUT-DTI={row['holdout_dti']:.4f} "
              f"ci=[{row['holdout_dti_ci95'][0]:.4f},{row['holdout_dti_ci95'][1]:.4f}]",
              flush=True)

    # ---- ranking
    ranked = sorted(out, key=lambda r: -(r["holdout_dti"] or 0))
    ours_row = next((r for r in out if r["label"].startswith("OURS")), None)
    scored = [r for r in out if isinstance(r["organizer_confirmed_score"], float)]
    best_other = next((r for r in ranked if not r["label"].startswith("OURS")), None)

    doc = dict(
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        holdout_version=holdout.HOLDOUT_VERSION,
        protocol=dict(alpha=holdout.ALPHA, beta=holdout.BETA, radius_px=holdout.RADIUS_PX,
                      n_folds=args.folds, frac_withheld=0.35, buffer_px=3,
                      emitter="FROZEN: dot mask read from disk, per-fold visible "
                              "catalogue subtracted exactly as for our arms"),
        information_advantage_note=(
            "Frozen artifacts were built with the full catalogue in hand, so they "
            "are information-advantaged versus our arms, which see only the "
            "per-fold visible catalogue. For registry files the bias runs against "
            "them: they were built to sit OFF the mapped catalogue, so avoiding "
            "the withheld truth lowers their holdout DTI."),
        label_convention=("Every number here is HOLDOUT-DTI (evaluator "
                          f"{holdout.HOLDOUT_VERSION}). Column "
                          "'organizer_confirmed_score' is ORGANIZER-CONFIRMED, "
                          "copied from registry/organizer_scores.json. The two are "
                          "different quantities and are never interchanged."),
        rows=ranked,
        summary=dict(
            ours_dti=(ours_row or {}).get("holdout_dti"),
            ours_dots=(ours_row or {}).get("n_dots"),
            best_other_dti=(best_other or {}).get("holdout_dti"),
            best_other_label=(best_other or {}).get("label"),
            best_other_organizer_score=(best_other or {}).get("organizer_confirmed_score"),
            ours_beats_best_other=(bool(ours_row and best_other and
                                        ours_row["holdout_dti"] > best_other["holdout_dti"])),
            n_scored_artifacts_evaluated=len(scored),
            rank_of_ours=(ranked.index(ours_row) + 1) if ours_row in ranked else None,
            n_artifacts=len(ranked),
        ),
        elapsed_seconds=round(time.time() - t0, 1),
    )
    p = Path(args.ev) / "e9_frozen_artifact_holdout.json"
    p.write_text(json.dumps(doc, indent=2, default=str) + "\n")
    print(f"\n[cmp] wrote {p} ({doc['elapsed_seconds']}s)")
    print("[cmp] " + json.dumps(doc["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
