#!/usr/bin/env python3
"""EXPERIMENT 1 - does a locally computable instrument predict the live portal score?

The group has 15 artifacts with OWNER-REPORTED portal scores
(`60GEMSDOE registry/audit_index.json`).  Every one of them is present as bytes.
Instrument B (SGMC 1:750k traces minus the competition catalogue) is a public,
independent compilation of faults that are mapped but NOT in the catalogue --
exactly the class the competition scores.  This script measures, for each
artifact, the *exact* DTI of its bytes against instrument B using the group's
shared metric module (`lane62/src/gems62/metric.py`, a verbatim transcription of
the published formula), and then compares the ranking with the portal.

Nothing here is a score for a file of ours.  It is a calibration of an
instrument against 15 outside numbers.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lane62" / "src"))
from gems62.metric import dti_exact          # shared tool, not forked
from gems62.holdout import sgmc_truth

G60 = Path("/tmp/g60/x/60GEMSDOE-main")
GRID_TF = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)


def read(path):
    with rasterio.open(path) as d:
        assert (d.height, d.width) == (3730, 3292), (path, d.height, d.width)
        a = d.read(1).astype(np.float64)
    a[~np.isfinite(a)] = 0.0
    return a


def main():
    t0 = time.time()
    cat = read(ROOT / "data" / "labels.tif")          # -1 nodata / 0 / 1
    catalogue = cat == 1.0
    footprint = read(ROOT / "data" / "sample_submission.tif")
    with rasterio.open(ROOT / "data" / "sample_submission.tif") as d:
        fp = np.isfinite(d.read(1)) | (d.read(1) == 1.0)
    fp = np.isfinite(footprint) & (footprint >= 0)
    valid = fp
    sgmc = read(G60 / "data" / "external" / "derived_sgmc_faults_100m.tif")
    b_raw = sgmc > 0
    truthB = sgmc_truth(sgmc, catalogue, valid)
    print(f"catalogue px {int(catalogue.sum()):,}  footprint px {int(valid.sum()):,}")
    print(f"SGMC raw px {int(b_raw.sum()):,}  instrument-B truth px {int(truthB.sum()):,}"
          f"  ({100*truthB.sum()/valid.sum():.3f}% of footprint)")
    idx = json.loads((G60 / "registry" / "audit_index.json").read_text())
    rows = []
    for r in idx:
        if r.get("owner_reported_score") is None:
            continue
        p = G60 / r["file"]
        if not p.exists():
            print("MISSING", p); continue
        pred = read(p)
        m = float((pred > 0).sum())
        # A/B/C: exact DTI of these bytes against instrument B, catalogue masked
        res = dti_exact(pred, truthB, valid=valid, known=catalogue)
        rows.append(dict(
            score=float(r["owner_reported_score"]), repo=r["repo"], sub=r["submission"],
            file=str(p.relative_to(G0 := G60)), n_dots=int(m),
            T=res["tp"], F=res["fp"], K=res["n_truth"], dti_B=res["dti"],
            credit_per_dot=res["tp"] / m if m else 0.0,
            sum_pred=float(pred.sum()),
        ))
        print(f"  {rows[-1]['score']:.4f} {r['repo']:<10} dots {int(m):>7,} "
              f"DTI_B {res['dti']:.6f} c/dot {rows[-1]['credit_per_dot']:.4f}")
    out = P = ROOT / "datum62" / "evidence" / "calibration_vs_portal.json"
    P.write_text(json.dumps(dict(
        experiment="instrument calibration against 15 owner-reported portal scores",
        instrument_B="SGMC 1:750k traces minus competition catalogue",
        truth_px_B=int(truthB.sum()),
        metric_module="lane62/src/gems62/metric.py::dti_exact (shared tool)",
        rows=rows, wall_s=time.time() - t0), indent=1))
    print("wrote", P, f"{time.time()-t0:.1f}s")
    # Spearman by hand
    import itertools
    s = np.array([r["score"] for r in rows]); x = np.array([r["dti_B"] for r in rows])
    def spearman(a, b):
        ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
        ra -= ra.mean(); rb -= rb.mean()
        return float((ra @ rb) / np.sqrt((ra @ ra) * (rb @ rb)))
    print("Spearman(portal, DTI_B) =", round(spearman(s, x), 4))
    print("Spearman(portal, credit/dot) =", round(spearman(s, np.array([r['credit_per_dot'] for r in rows])), 4))
    for r in sorted(rows, key=lambda r: -r["dti_B"]):
        print(f"  DTI_B {r['dti_B']:.5f}  portal {r['score']:.4f}  {r['repo']:<10} {r['sub'][:40]}")


if __name__ == "__main__":
    main()
