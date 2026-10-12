#!/usr/bin/env python3
"""Hide-and-recover holdout for the datum-offset lane.

Protocol (from the session brief, applied to a catalogue-free detector)
----------------------------------------------------------------------
* withhold whole fault *segments* with a buffer.  Operational definition, stated explicitly
  because the catalogue is ONE basin-scale connected lineament network (measured: connected
  components of `existing_faults.tif` are 10^5-10^6 px, so a component-level rule matches
  nothing): the *segment* is the catalogue geometry inside the fold block, and the block is
  eroded by `buffer_px` before withholding, so (a) fault geometry is never cut and scored at an
  arbitrary boundary, and (b) no withholding decision is made on the basis of geometry outside
  the block.  Catalogue connected components that lie
  were also withheld as a whole under an earlier rule that additionally required a component to
  lie wholly inside the block; that rule was tested and rejects every fold (0 withheld pixels), so
  it is recorded here as a dead end rather than used.
  `buffer_px` defaults to 3 = one 300 m kernel radius, i.e. the leakage-length scale of the
  published metric;
* "derive every catalogue-based feature only from the visible faults": the datum lane derives
  *nothing* from the catalogue, so this clause is satisfied by construction -- which is exactly
  what the leakage canary below verifies rather than assumes;
* mask visible faults pixel-exactly (`active = footprint & ~visible_catalogue`);
* score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel) of the lane's emission
  against the withheld truth, pooled over folds (sum of TP_w, FP_w, FN_w across folds);
* leakage canary: AUC of each stand-alone feature against the withheld truth.  AUC > 0.90 is
  treated as leakage until proven otherwise.

Truth here is the *visible catalogue*, so this instrument cannot reward a genuinely new fault
(it is a proxy; the same caveat the sibling repositories record).  It answers a narrower and
still useful question: does the datum lane's emission sit on real faults at better than chance
when those faults are hidden from it?

Usage:
  python scripts/run_holdout.py --emission build/lane/<name>.tif \
      --catalogue /home/user/work/bridge/existing_faults.tif \
      --sample /home/user/work/bridge/example_submission.tif --out build/holdout.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from gems62 import grid, metric  # noqa: E402


def auc(score: np.ndarray, pos: np.ndarray, neg: np.ndarray) -> float:
    """Rank AUC with tie handling (Mann-Whitney)."""
    s = score[pos]; n = score[neg]
    if s.size == 0 or n.size == 0:
        return float("nan")
    allv = np.concatenate([s, n])
    order = np.argsort(allv, kind="mergesort")
    ranks = np.empty(allv.size, float)
    ranks[order] = np.arange(1, allv.size + 1)
    # average ranks for ties
    uniq, inv, cnt = np.unique(allv, return_inverse=True, return_counts=True)
    if (cnt > 1).any():
        sums = np.zeros(uniq.size); np.add.at(sums, inv, ranks)
        ranks = (sums / cnt)[inv]
    r_pos = ranks[:s.size].sum()
    return float((r_pos - s.size * (s.size + 1) / 2) / (s.size * n.size))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emission", required=True)
    ap.add_argument("--catalogue", required=True)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--out", default="build/holdout.json")
    ap.add_argument("--folds", type=int, default=6)
    ap.add_argument("--min-fault-px", type=int, default=250)
    ap.add_argument("--buffer-px", type=int, default=3)
    ap.add_argument("--fields", default=None,
                    help="optional .npz of same-shape 100 m feature arrays; each is scored "
                         "stand-alone against the withheld truth (the protocol's leakage canary: "
                         "AUC > 0.90 means leakage until proven otherwise)")
    args = ap.parse_args()

    import rasterio
    from scipy import ndimage

    known, _ = grid.load_catalogue(args.catalogue)
    with rasterio.open(args.sample) as s:
        footprint = np.isfinite(s.read(1))
    with rasterio.open(args.emission) as s:
        emis = s.read(1) > 0
    H, W = known.shape

    rows = np.nonzero(footprint.any(1))[0]; cols = np.nonzero(footprint.any(0))[0]
    r0, r1 = rows.min(), rows.max() + 1
    c0, c1 = cols.min(), cols.max() + 1
    # spatial folds: 2 columns x 3 rows over the footprint bounding box (rows ~ north-south)
    fr = 3; fc = max(1, args.folds // fr)
    edges_r = np.linspace(r0, r1, fr + 1).astype(int)
    edges_c = np.linspace(c0, c1, fc + 1).astype(int)

    folds = []
    comp_labels, n_comp = ndimage.label(known, structure=np.ones((3, 3), int))
    comp_px = np.bincount(comp_labels.ravel())
    for i in range(fr):
        for j in range(fc):
            inner = np.zeros((H, W), bool)
            rr0, rr1 = edges_r[i], edges_r[i + 1]
            cc0, cc1 = edges_c[j], edges_c[j + 1]
            inner[rr0:rr1, cc0:cc1] = True
            interior = ndimage.binary_erosion(inner, iterations=args.buffer_px, border_value=0)
            interior &= footprint
            if not interior.any():
                continue
            # label the catalogue only within the block + buffer band, then withhold whole
            # components whose majority lies inside the block
            truth = known & interior
            if int(truth.sum()) < args.min_fault_px:
                continue
            # Scored domain = the whole eroded block.  Inside it there is no "visible" catalogue
            # to exclude: the entire catalogue geometry in the block is the withheld truth.  (The
            # module's `active` = footprint-minus-known convention belongs to the *organizer's*
            # task, where the catalogue is masked out; a holdout must score the masked geometry
            # instead -- passing `interior & ~known` here silently zeroes the truth.)
            active = interior
            if int(truth.sum()) < args.min_fault_px or not active.any():
                continue
            res = metric.dti_binary(emis, truth, active)
            folds.append(dict(fold=[i, j], rows=[int(rr0), int(rr1)], cols=[int(cc0), int(cc1)],
                              n_truth=int(res["n_truth"]), n_pred=int(res["n_active_pred"]),
                              tp=res["tp"], fp=res["fp"], fn=res["fn"], dti=res["dti"],
                              recall=res["tp"] / max(res["n_truth"], 1)))
            del inner, interior, truth, active
    # pooled DTI: sum the components across folds then apply the published formula once
    tp = sum(f["tp"] for f in folds); fp = sum(f["fp"] for f in folds); fn = sum(f["fn"] for f in folds)
    pooled = metric.dti_from_components(tp, fp, fn)

    # ---- leakage canary on stand-alone features -------------------------------------------
    # feature 1: lane proximity = distance to the nearest emitted dot (kernel-weighted)
    dist_pred = ndimage.distance_transform_edt(~emis)
    feat_prox = metric.kernel(dist_pred)            # 1 on a dot, 0 beyond 300 m
    # feature 2: pure DEM evidence carried by the emission geometry (1 on dots, 0 elsewhere)
    feat_mask = emis.astype(np.float32)
    canary = {}
    for name, f in (("lane_kernel_proximity", feat_prox), ("lane_binary_mask", feat_mask)):
        aucs = []
        for fold in folds:
            rr0, rr1 = fold["rows"]; cc0, cc1 = fold["cols"]
            inner = np.zeros((H, W), bool); inner[rr0:rr1, cc0:cc1] = True
            interior = ndimage.binary_erosion(inner, iterations=args.buffer_px, border_value=0)
            interior &= footprint
            truth = (known & interior).ravel()
            # negatives come from the SAME fold interior, never basin-wide
            active = (interior & ~known).ravel()
            val = f.ravel()
            pos = np.nonzero(truth)[0]
            neg = np.nonzero(active)[0]
            stride = max(1, neg.size // 200000)
            aucs.append(auc(val, pos, neg[::stride]))
        canary[name] = dict(auc_per_fold=[float(a) for a in aucs],
                            auc_mean=float(np.nanmean(aucs)) if aucs else None,
                            verdict=("LEAKAGE-SUSPECT" if (np.nanmean(aucs) if aucs else 0) > 0.90
                                     else "ok"))
    extra_canary: dict[str, dict] = {}
    if args.fields:
        fz = np.load(args.fields)
        for name in fz.files:
            f = np.asarray(fz[name], np.float32)
            if f.shape != (H, W):
                extra_canary[name] = dict(error=f"shape {f.shape} != {(H, W)}")
                continue
            f = np.nan_to_num(f, nan=0.0, posinf=0.0, neginf=0.0).ravel()
            aucs = []
            for fold in folds:
                rr0, rr1 = fold["rows"]; cc0, cc1 = fold["cols"]
                inner = np.zeros((H, W), bool); inner[rr0:rr1, cc0:cc1] = True
                interior = ndimage.binary_erosion(inner, iterations=args.buffer_px, border_value=0)
                interior &= footprint
                pos = np.nonzero((known & interior).ravel())[0]
                neg = np.nonzero((interior & ~known).ravel())[0]
                stride = max(1, neg.size // 200000)
                aucs.append(auc(f, pos, neg[::stride]))
            mean = float(np.nanmean(aucs)) if aucs else float("nan")
            extra_canary[name] = dict(auc_per_fold=[float(a) for a in aucs], auc_mean=mean,
                                       verdict="LEAKAGE-SUSPECT" if mean > 0.90 else "ok")
        canary["user_fields"] = extra_canary

    report = dict(
        emission=pathlib.Path(args.emission).name,
        emission_sha256=grid.sha256(args.emission),
        protocol=dict(folds=len(folds), buffer_px=args.buffer_px, truth="visible catalogue",
                      masking="visible catalogue pixel-exact",
                      alpha=metric.ALPHA, beta=metric.BETA, kernel_radius_px=metric.RADIUS_PX),
        pooled=dict(tp=tp, fp=fp, fn=fn, dti=pooled,
                    n_truth=sum(f["n_truth"] for f in folds),
                    n_pred=sum(f["n_pred"] for f in folds)),
        folds=folds, canary=canary,
        note=("proxy instrument: truth is the visible catalogue, so a genuinely new fault cannot "
              "be rewarded here; a positive result licenses packaging, never a score claim"),
    )
    out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))
    print(json.dumps({k: report[k] for k in ("protocol", "pooled", "canary")}, indent=1))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
