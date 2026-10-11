#!/usr/bin/env python3
"""Recompute the final holdout statistics for the two shipped candidates with the
corrected (fail-closed) bootstrap, and merge the uniqueness-gate results into
docs/data/site.json.

Separated from scripts/finalize.py so the statistics can be recomputed without
re-running the (slow) registry scan, and so a reviewer can see that the shipped
numbers come from the bytes on disk.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems62 import grid as G          # noqa: E402
from gems62 import holdout as H       # noqa: E402
from gems62.metric import kernel, credit_bar, dti_exact   # noqa: E402

HIDDEN_MASS_PX = 7905
DL = ROOT / "docs/downloads"


def per_dot(pred, truth, g):
    gg = truth & g.footprint & ~g.catalogue
    p = pred & g.footprint & ~g.catalogue
    ys, xs = np.nonzero(p)
    if ys.size == 0:
        return np.array([])
    dg = ndi.distance_transform_edt(~gg)
    return kernel(dg[ys, xs])


def main():
    g = G.load_grid(ROOT)
    h, w = g.footprint.shape
    with rasterio.open(ROOT / "data/external/derived_sgmc_faults_100m.tif") as d:
        sgmc = d.read(1)
    truthB = H.sgmc_truth(sgmc, g.catalogue, g.footprint)
    tr_ys, tr_xs = np.nonzero(truthB)
    nsub = min(HIDDEN_MASS_PX, tr_ys.size)
    draws = []
    for k in range(10):
        rk = np.random.default_rng(1000 + k)
        selk = rk.choice(tr_ys.size, nsub, replace=False)
        m = np.zeros((h, w), bool); m[tr_ys[selk], tr_xs[selk]] = True
        draws.append(m)

    site = json.load(open(ROOT / "docs/data/site.json"))

    def stats(pred):
        A = H.hide_and_recover(pred, g.catalogue, g.footprint, rows=2, cols=2)
        B = dti_exact(pred.astype(float), truthB, valid=g.footprint, known=g.catalogue)
        bp = float(np.mean([dti_exact(pred.astype(float), mk, valid=g.footprint,
                                      known=g.catalogue)["dti"] for mk in draws]))
        kb = per_dot(pred, truthB, g)
        return dict(n_dots=int(pred.sum()),
                    instrumentA=A["pooled"], instrumentA_ci95=A["ci95"],
                    n_truth_A=A["n_truth_px"],
                    instrumentA_note="truth = whole catalogue segments hidden by a 2x2 spatial "
                                     "block and dilated by the 300 m kernel radius; visible "
                                     "catalogue masked; pooled over the whole grid",
                    instrumentB=B, instrumentB_ci_placeholder=None,
                    instrumentB_prime_dti=bp, hidden_mass_px=nsub,
                    mean_credit_per_dot=float(kb.mean()) if kb.size else 0.0,
                    median_credit_per_dot=float(np.median(kb)) if kb.size else 0.0,
                    frac_dots_clearing_bar_at_0p2778=float((kb > credit_bar(0.2778)).mean()) if kb.size else 0.0,
                    credit_bar_at_s_0p2778=credit_bar(0.2778))

    for key, name in (("primary", "gems62-lahontan-datum-break-dotted-primary-zeros.tif"),
                      ("secondary", "gems62-lahontan-flagged-breaks-selective-secondary-zeros.tif")):
        with rasterio.open(DL / name) as d:
            arr = d.read(1)
        pred = np.nan_to_num(arr, nan=0.0) > 0
        st = stats(pred)
        # same-stratum random control
        rng = np.random.default_rng(11)
        sidx = np.flatnonzero(ndi.binary_dilation(pred, iterations=3) & g.active)
        sA, sB, sBp = [], [], []
        for _ in range(5):
            ctrl = np.zeros((h, w), bool)
            ctrl.ravel()[rng.choice(sidx, min(int(pred.sum()), sidx.size), replace=False)] = True
            sA.append(H.hide_and_recover(ctrl, g.catalogue, g.footprint, rows=2, cols=2)["pooled"]["dti"])
            sB.append(dti_exact(ctrl.astype(float), truthB, valid=g.footprint, known=g.catalogue)["dti"])
            sBp.append(float(np.mean([dti_exact(ctrl.astype(float), mk, valid=g.footprint,
                                                known=g.catalogue)["dti"] for mk in draws])))
        st["control_same_stratum"] = dict(
            instrumentA=float(np.mean(sA)), instrumentB=float(np.mean(sB)),
            instrumentB_prime=float(np.mean(sBp)),
            edge_instrumentA=st["instrumentA"]["dti"] - float(np.mean(sA)),
            edge_instrumentB=st["instrumentB"]["dti"] - float(np.mean(sB)),
            edge_instrumentB_prime=st["instrumentB_prime_dti"] - float(np.mean(sBp)),
            description="random pixels from the 3 px dilation of this file's own positives "
                        "(same spatial stratum), matched dot count, 5 realisations")
        site["files"][key]["stats"] = st
        print(f"{key}: n={st['n_dots']}  A={st['instrumentA']['dti']:.6f} "
              f"CI {st['instrumentA_ci95'][0]:.6f}-{st['instrumentA_ci95'][1]:.6f}  "
              f"B={st['instrumentB']['dti']:.6f}  B'={st['instrumentB_prime_dti']:.6f}  "
              f"edges A {st['control_same_stratum']['edge_instrumentA']:+.6f} "
              f"B {st['control_same_stratum']['edge_instrumentB']:+.6f} "
              f"B' {st['control_same_stratum']['edge_instrumentB_prime']:+.6f}")

    # merge the uniqueness gate if it has finished
    gate_p = ROOT / "evidence/uniqueness_gate.json"
    if gate_p.exists():
        gate = json.load(open(gate_p))
        site["gate"] = gate
        for key, name in (("primary", "gems62-lahontan-datum-break-dotted-primary-zeros.tif"),
                          ("secondary", "gems62-lahontan-flagged-breaks-selective-secondary-zeros.tif")):
            if name in gate:
                site["files"][key]["uniqueness"] = {k: v for k, v in gate[name].items() if k != "rows"}
        print("merged uniqueness gate")
    else:
        print("WARNING: uniqueness gate not present yet")

    json.dump(site, open(ROOT / "docs/data/site.json", "w"), indent=1, default=str)
    print("wrote docs/data/site.json")


if __name__ == "__main__":
    main()
