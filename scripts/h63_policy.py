#!/usr/bin/env python3
"""H63M — choose the emission density and mass on the calibrated proxy instrument.

`h63_emit.py --stage measure` fixed the belief fields.  This script sweeps the two
remaining policy axes -- **non-maximum-suppression radius** (how densely the dots are
packed along a lineament) and **emitted mass** -- and reports, for every candidate:

* ``cm_proxy``  -- MEASURED credit per unit mass against USGS SGMC off-catalogue faults;
* ``lift``      -- MEASURED, over a random emission restricted to the same off-catalogue
                   domain at the same mass;
* ``projected_dti`` -- MODEL: ``r * cm_proxy / (alpha + beta*K/S)`` with the transfer
                   ratio ``r`` and the hidden-truth mass ``K`` swept over the range the
                   registry calibration supports (r 0.478 - 0.775, K 8000 - 12000).

The metric rewards density along a *true* line: every emitted cell that sits on a hidden
fault pixel returns full kernel credit and zero false-positive mass, so packing dots
tightly along a corroborated lineament is free.  It is not free when the lineament is
wrong, which is exactly what the sweep measures.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np
from scipy import ndimage as ndi

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from gems62.metric import dti_components, ALPHA, BETA, RADIUS_M  # noqa: E402
from gems62.grid import HEIGHT, WIDTH, PIXEL_M  # noqa: E402

OUT = HERE / "data" / "h63"
EV = HERE / "evidence"
R_LO, R_HI = 0.478, 0.775        # MODEL range, evidence/h63_calibration.json
K_LO, K_HI = 8000.0, 12000.0
MASSES = [20000, 40000, 60000, 90000, 130000, 180000]
RADII = [0, 1, 2, 3, 4]


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def nms_peaks(p, radius_px, valid):
    if radius_px <= 0:
        return valid & np.isfinite(p) & (p > 0)
    size = 2 * int(radius_px) + 1
    mx = ndi.maximum_filter(np.where(valid, p, -np.inf), size=size, mode="constant", cval=-np.inf)
    return valid & np.isfinite(p) & (p >= mx) & (p > 0)


def topk(mask, p, k):
    idx = np.flatnonzero(mask.ravel())
    if idx.size <= k:
        return mask
    v = p.ravel()[idx]
    keep = idx[np.argpartition(-v, k - 1)[:k]]
    o = np.zeros(mask.size, bool)
    o[keep] = True
    return o.reshape(mask.shape)


def main() -> int:
    t0 = time.time()
    usable = np.load(OUT / "valid_mask.npy")
    pro = np.load(OUT / "proxy_off.npy")
    cat = np.load(OUT / "catalogue.npy")
    dcat = (ndi.distance_transform_edt(~cat) * PIXEL_M).astype(np.float32)
    offcat = usable & (dcat >= 300)

    fields = {}
    for p in sorted(OUT.glob("h63_belief_*.npy")):
        fields[p.stem.replace("h63_belief_", "")] = np.load(p)
    log("fields: " + ", ".join(sorted(fields)))

    rng = np.random.default_rng(62)
    flat = np.flatnonzero(offcat.ravel())

    def score_mask(m):
        m = m & usable
        S = float(m.sum())
        c = dti_components(m.astype(np.float32), pro, valid=usable,
                           pixel_size_m=PIXEL_M, radius_m=RADIUS_M)
        return S, c.tp_w, (c.tp_w / S if S else 0.0)

    ctrl = {}
    for M in MASSES:
        c = np.zeros(offcat.size, bool)
        c[flat[rng.choice(flat.size, size=M, replace=False)]] = True
        S, tp, cm = score_mask(c.reshape(offcat.shape))
        ctrl[M] = cm
    log("random off-catalogue control cm: " + json.dumps(
        {str(k): round(v, 4) for k, v in ctrl.items()}))

    rows = []
    for fname, f in sorted(fields.items()):
        for r in RADII:
            pk = nms_peaks(np.where(offcat, f, -np.inf), r, offcat)
            for M in MASSES:
                m = topk(pk, f, M)
                S, tp, cm = score_mask(m)
                if S < 100:
                    continue
                lift = cm / ctrl[M] if ctrl[M] else float("nan")
                proj_hi = R_HI * cm / (ALPHA + BETA * K_LO / S)
                proj_lo = R_LO * cm / (ALPHA + BETA * K_HI / S)
                rows.append(dict(field=fname, radius_px=r, mass_target=M, mass=S,
                                 cm_proxy=round(cm, 5), lift=round(lift, 3),
                                 proj_dti_optimistic=round(proj_hi, 4),
                                 proj_dti_conservative=round(proj_lo, 4),
                                 proj_dti_mid=round((proj_hi + proj_lo) / 2, 4)))
        best = max((r for r in rows if r["field"] == fname), key=lambda d: d["proj_dti_mid"])
        log(f"  {fname:12s} best r={best['radius_px']} M={best['mass']:.0f} "
            f"cm={best['cm_proxy']:.4f} lift={best['lift']:.2f}x "
            f"proj[{best['proj_dti_conservative']:.3f},{best['proj_dti_optimistic']:.3f}]")

    rows.sort(key=lambda d: -d["proj_dti_mid"])
    res = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_class": ("MEASURED (cm_proxy, lift) + MODEL (projected DTI over "
                           f"r in [{R_LO}, {R_HI}] and K in [{K_LO:.0f}, {K_HI:.0f}]; a "
                           "projection is never a score)"),
        "random_control_cm": {str(k): round(v, 5) for k, v in ctrl.items()},
        "rows": rows,
        "seconds": round(time.time() - t0, 1),
    }
    (EV / "h63_policy.json").write_text(json.dumps(res, indent=1))
    log("\nTOP 15 by mid projection:")
    for r in rows[:15]:
        log(f"  {r['field']:12s} r={r['radius_px']} M={r['mass']:7.0f} cm={r['cm_proxy']:.4f} "
            f"lift={r['lift']:.2f}x proj[{r['proj_dti_conservative']:.3f},"
            f"{r['proj_dti_optimistic']:.3f}]")
    log("wrote " + str(EV / "h63_policy.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
