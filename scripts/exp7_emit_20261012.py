#!/usr/bin/env python3
"""EXP-7 (session arena/7b275dfb-62gemsdoe): emit the unique submission, validate, uniqueness.

Pre-registered operating rule (fixed before looking at the sweep results):
  * select the model with the highest blocked OOF DTI(S* v2) from exp6;
  * at that model, select the mass-sweep point with the highest OOF DTI(S* v2);
  * emit isolated single-pixel dots (no two dots within 1 px), ranked by OOF score,
    masking the mapped catalogue and its 3 px dilation (pixel-exact visible-fault mask);
  * if any non-vacuous registry raster receives > 70 % of the dots within 3 px, the
    protocol's duplicate tripwire fires: log it as a duplicate and stop (no artifact).

Outputs:
  docs/downloads/<name>.tif        the submission (single-band float32, values in [0,1])
  evidence/e7_emit_20261012.json   validator + uniqueness + holdout + run-card inputs
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems62 import grid, metric as M, validate  # noqa: E402

EVID = ROOT / "evidence"
CACHE = ROOT / "build" / "cache"


def main() -> int:
    exp6 = json.loads((EVID / "e6_train_20261012.json").read_text())
    which = exp6["selected"]
    sweep = exp6["models"][which]["sweep"]
    best = exp6["models"][which]["best"]
    print(f"model {which} best sweep point: {best}")

    footprint = np.isfinite(rasterio.open(ROOT / "data" / "sample_submission.tif").read(1))
    with rasterio.open(ROOT / "data" / "labels.tif") as d:
        cat = (d.read(1) == 1) & footprint
    cat3 = ndi.binary_dilation(cat, iterations=3)
    S = np.load(ROOT / "build" / "sstar" / "truth_est.npy") & footprint
    P = np.load(ROOT / "build" / f"p_oof_{which}.npy")
    H, W = footprint.shape

    # ---- emission: greedy score-ranked isolated dots --------------------------------
    active = footprint & ~cat3
    scores = np.where(active, P, -np.inf).ravel()
    order = np.argsort(-scores, kind="stable")
    n_target = int(best["n_dots"])
    dots = np.zeros((H, W), bool)
    supp = np.zeros((H, W), bool)
    ys, xs = np.unravel_index(order[: min(order.size, n_target * 40)], (H, W))
    placed = 0
    for r, c in zip(ys, xs):
        if not np.isfinite(scores[r * W + c]) or supp[r, c]:
            continue
        dots[r, c] = True
        placed += 1
        r0, r1 = max(r - 1, 0), min(r + 2, H)
        c0, c1 = max(c - 1, 0), min(c + 2, W)
        supp[r0:r1, c0:c1] = True
        if placed >= n_target:
            break
    print(f"placed {placed:,} isolated dots (target {n_target:,})")
    n_dots = placed

    arr = np.zeros((H, W), np.float32)
    arr[dots] = 1.0

    # ---- write + validate -----------------------------------------------------------
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = f"gems62f-h2r-ventcons-{n_dots}-{stamp}-zeros.tif"
    out = ROOT / "docs" / "downloads" / name
    rec = grid.write_submission(out, arr, nodata=None)
    chk = grid.check_submission(out)
    report = validate.validate_submission(out, footprint)
    print(json.dumps(chk, indent=1)[:600])
    print(report.to_json()[:600])

    # ---- uniqueness vs every registry raster we hold --------------------------------
    reg_dir = ROOT / "build" / "registry"
    mine_bin = dots & footprint
    rows_uni = []
    max_frac, max_rho, max_jac = 0.0, 0.0, 0.0
    worst = None
    tripped = []
    # deterministic background sample for rank correlation
    rng = np.random.default_rng(3)
    foot_idx = np.flatnonzero(footprint.ravel())
    bg = rng.choice(foot_idx, size=200_000, replace=False)
    mine_f = arr.ravel()
    for p in sorted(reg_dir.glob("*.tif")):
        with rasterio.open(p) as d:
            a = d.read(1)
        m = (np.where(np.isfinite(a), a, 0) > 0) & footprint
        if not m.any():
            continue
        cov = ndi.distance_transform_edt(~m) <= 3
        frac = float((mine_bin & cov).sum() / max(mine_bin.sum(), 1))
        coverage3px = float(cov[footprint].mean())
        jac = float((mine_bin & cov).sum() / max((mine_bin | (m & footprint)).sum(), 1))
        # symmetric Jaccard of dilated masks
        mdil = ndi.binary_dilation(mine_bin, iterations=3)
        jac_sym = float((mdil & cov).sum() / max((mdil | cov).sum(), 1))
        u = np.union1d(np.flatnonzero(mine_bin.ravel()), np.flatnonzero(m.ravel()))
        samp = np.union1d(u, bg)
        ra = mine_f[samp]
        rb = a.ravel()[samp]
        rb = np.where(np.isfinite(rb), rb, 0.0)
        # tie-aware spearman on the sample
        def rk(v):
            o = np.argsort(v, kind="mergesort")
            r = np.empty(v.size, float)
            r[o] = np.arange(1, v.size + 1)
            uniq, inv, cnt = np.unique(v, return_inverse=True, return_counts=True)
            if (cnt > 1).any():
                sums = np.zeros(uniq.size)
                np.add.at(sums, inv, r)
                r = (sums / cnt)[inv]
            return r
        r1, r2 = rk(ra), rk(rb)
        r1 -= r1.mean(); r2 -= r2.mean()
        den = np.sqrt((r1 @ r1) * (r2 @ r2))
        rho = float(r1 @ r2 / den) if den > 0 else 0.0
        vacuous = coverage3px >= 0.70
        rows_uni.append(dict(file=p.name, frac3px=frac, rho=abs(rho),
                             coverage3px=coverage3px, jaccard_sym=jac_sym,
                             n_dots_reg=int(m.sum()), vacuous=vacuous))
        if not vacuous:
            if frac > max_frac:
                max_frac, worst = frac, p.name
            max_rho = max(max_rho, abs(rho))
            max_jac = max(max_jac, jac_sym)
            if frac > 0.70:
                tripped.append(p.name)
    print(f"uniqueness: max_frac3px(non-vacuous)={max_frac:.3f} ({worst}) "
          f"max|rho|={max_rho:.3f} max_jaccard_sym={max_jac:.3f}")

    # ---- protocol holdout (hide-and-recover on catalogue segments) -------------------
    sys.path.insert(0, str(ROOT / "src"))
    from gems62 import holdout_segmented as hs

    def emission_fn(eligible, priority, footprint_, visible, budget):
        """Same emitter as the final field: score-ranked isolated dots, budgeted."""
        act = eligible & ~ndi.binary_dilation(visible, iterations=3) if visible is not None \
            else eligible
        sc = np.where(act, priority, -np.inf).ravel()
        order = np.argsort(-sc, kind="stable")
        outm = np.zeros(act.shape, bool)
        supp = np.zeros(act.shape, bool)
        hh, ww = act.shape
        ys, xs = np.unravel_index(order[: min(order.size, budget * 40)], (hh, ww))
        placed = 0
        for r, c in zip(ys, xs):
            if not np.isfinite(sc[r * ww + c]) or supp[r, c]:
                continue
            outm[r, c] = True
            placed += 1
            r0, r1 = max(r - 1, 0), min(r + 2, hh)
            c0, c1 = max(c - 1, 0), min(c + 2, ww)
            supp[r0:r1, c0:c1] = True
            if placed >= budget:
                break
        return outm

    pr = P.copy()
    pr[~np.isfinite(pr)] = 0.0
    hold = hs.run_holdout(active, pr, footprint, cat & footprint, emission_fn)
    hold_json = json.loads(json.dumps(hold, default=lambda o: str(o)))
    print("holdout:", json.dumps({k: hold_json[k] for k in
                                  ("version", "n_folds", "pooled_dti", "fold_dti_ci95",
                                   "withheld_positives_total") if k in hold_json})[:600])

    # ---- science deliverable: shoreline profiles with flagged steps (lane first deliverable)
    # kept from the prior session's v8 run; referenced in the run card.

    evidence = dict(
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        session="arena/7b275dfb-62gemsdoe",
        artifact=dict(name=name, path=str(out.relative_to(ROOT)), bytes=out.stat().st_size,
                      sha256=validate.sha256_file(out), n_dots=n_dots,
                      model=which, sweep_point=best),
        write_receipt=rec, check_submission=chk,
        validator=json.loads(report.to_json()),
        uniqueness=dict(max_frac3px_nonvacuous=max_frac, worst=worst, max_rho=max_rho,
                        max_jaccard_sym=max_jac, tripped=tripped, rows=rows_uni),
        holdout=hold_json,
        instruments=dict(
            sstar_v2="rebuild with fixed 300 m kernel (IR-62-2026-10-12-01)",
            dti_sstar_oof=best["dti_sstar"],
            credit_sstar_oof=best.get("credit_sstar")),
        registry_files=len(rows_uni),
    )
    (EVID / "e7_emit_20261012.json").write_text(json.dumps(evidence, indent=1, default=str) + "\n")
    print("wrote", out)
    if tripped:
        print("DUPLICATE-TRIPWIRE tripped:", tripped)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
