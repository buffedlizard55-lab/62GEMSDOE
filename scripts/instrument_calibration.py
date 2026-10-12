#!/usr/bin/env python3
"""Experiment 1 — validate (or refute) a local scoring instrument against ORGANIZER scores.

Why this script exists
----------------------
IR-62-HOLDOUT-01 (previous session): the hide-and-recover holdout that withholds *catalogue*
pixels is ANTI-correlated with the organiser's score (Spearman -0.91 over 10 confirmed
artifacts).  That is expected: the competition scores faults that are **absent** from the
USGS/INGENIOUS catalogue, so a proxy whose truth *is* the catalogue rewards exactly the
population that cannot score.

This script asks the question the protocol requires before any number is trusted:

    Is there an independent, free, official truth set that RANKS the group's artifacts the
    same way the organiser does?

The candidate is `derived_sgmc_faults_100m.tif` (USGS State Geologic Map Compilation, 1:750 k,
rasterised on the competition grid) **minus** the competition catalogue.  It is an official
compilation that is independent of the organiser's catalogue and 4.8 % of it is off-catalogue
by pixel count (79,615 of 83,593 px) -- so it is a sample of "faults the catalogue does not
contain", which is the definition of the target population.

Method: score every registry probe whose owner-reported score is known with the SHARED
`gems62.metric` implementation (no private metric fork), then correlate.

Output: evidence/exp1_instrument_calibration.json
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import rasterio
from scipy.ndimage import binary_dilation, distance_transform_edt
from scipy.stats import spearmanr, pearsonr

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems62 import metric  # noqa: E402  (shared implementation, never forked)

PROBES = [
    # file, owner-reported score (OWNER-REPORTED, not an organiser receipt)
    ("data/probe/h33_2_b2_zeros.tif", 0.2778),
    ("data/probe/p36_pinn_38854_02750.tif", 0.2750),
    ("data/probe/p28_h274_40199_02708.tif", 0.2708),
    ("data/probe/p28_h321_42294_02649.tif", 0.2649),
    ("data/probe/p33_h33d_41865_02632.tif", 0.2632),
    ("data/probe/d25_dotted_h195_d28_zeros.tif", 0.2600),
    ("data/probe/p24_h251_d15_60069_02477.tif", 0.2477),
    ("data/probe/p27_gapclosure_61328_02449.tif", 0.2449),
    ("data/probe/p49_gateortho_40000_02376.tif", 0.2376),
    ("data/probe/p19_h195_121131_01922.tif", 0.1922),
    ("data/probe/p19_h194_123779_01894.tif", 0.1894),
    ("data/probe/p20_h201_123829_01890.tif", 0.1890),
    ("data/probe/p16_h161_123939_01855.tif", 0.1855),
]


def load_mask(path: str) -> tuple[np.ndarray, np.ndarray]:
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float32)
    finite = np.isfinite(a)
    return (a > 0) & finite, finite


def poisson_hardcore(footprint: np.ndarray, n: int, min_px: float, seed: int) -> np.ndarray:
    """Uniform random dots inside footprint with a hard-core minimum separation.

    Grid-based: a candidate is accepted only if no accepted dot lies within
    ``min_px`` (checked on the integer lattice), so the test is a 7x7 window
    maximum rather than a tree query.  This is a Matérn hard-core process, the
    null the brief asks for.
    """
    rng = np.random.default_rng(seed)
    ys, xs = np.nonzero(footprint)
    order = rng.permutation(len(ys))
    out = np.zeros(footprint.shape, bool)
    r = int(np.ceil(min_px))
    dil = np.zeros(footprint.shape, bool)
    placed = 0
    for idx in order:
        y, x = int(ys[idx]), int(xs[idx])
        y0, y1 = max(0, y - r), min(out.shape[0], y + r + 1)
        x0, x1 = max(0, x - r), min(out.shape[1], x + r + 1)
        if dil[y0:y1, x0:x1].any():
            continue
        out[y, x] = True
        dil[y0:y1, x0:x1] = True
        placed += 1
        if placed >= n:
            break
    return out


def main() -> int:
    cat = rasterio.open(ROOT / "data/existing_faults.tif").read(1)
    footprint = cat != -1
    poscat = (cat == 1) & footprint
    sgmc = rasterio.open(ROOT / "data/external/derived_sgmc_faults_100m.tif").read(1) > 0
    sgmc &= footprint

    report: dict = {
        "experiment": "E1 instrument calibration",
        "instrument": "SGMC 1:750k compilation MINUS the competition catalogue",
        "metric": "gems62.metric.dti_components (alpha 0.2, beta 0.8, 300 m triangular)",
        "truth_pixels_off_catalogue": int((sgmc & ~poscat).sum()),
        "truth_pixels_total": int(sgmc.sum()),
        "catalogue_pixels": int(poscat.sum()),
        "variants": {},
    }

    for buf in (0, 3):
        if buf:
            strel = np.ones((2 * buf + 1, 2 * buf + 1), bool)
            known = binary_dilation(poscat, strel)
        else:
            known = poscat.copy()
        # shared metric signature: dti_components(pred, truth, valid=...)
        # The scored domain is the footprint minus the known-fault buffer; the
        # metric ANDs truth with `valid`, so masking the domain is the only
        # mechanism needed.
        domain = footprint & ~known
        truth_sgmc = sgmc.astype(np.float32)
        truth_cat = poscat.astype(np.float32) if buf == 0 else None

        rows = []
        for path, score in PROBES:
            p = ROOT / path
            if not p.is_file():
                continue
            mask, _ = load_mask(str(p))
            pred = mask.astype(np.float32)
            c = metric.dti_components(pred, truth_sgmc, valid=domain)
            M = int(mask.sum())
            credit = float(c.tp_w / M) if M else 0.0
            row = dict(
                file=pathlib.Path(path).name, owner_reported_score=score, M=M,
                dti_sgmc=c.dti, tp=c.tp_w, fp=c.fp_w, fn=c.fn_w,
                coverage=float(c.tp_w / max(c.tp_w + c.fn_w, 1e-9)),
                mean_credit_per_dot=credit,
            )
            if truth_cat is not None:
                cc = metric.dti_components(pred, truth_cat, valid=domain)
                row["dti_catalogue"] = cc.dti
            rows.append(row)

        # controls: a TRUE Poisson hard-core control this time (see IR-62-POISSON)
        ctrl = {}
        for M, seed in ((37654, 11), (44090, 12)):
            mask = poisson_hardcore(domain, M, 3.0, seed)
            pred = mask.astype(np.float32)
            c = metric.dti_components(pred, truth_sgmc, valid=domain)
            ctrl[f"poisson300m_offcat_M{M}"] = dict(
                M=int(mask.sum()), dti_sgmc=c.dti,
                mean_credit_per_dot=float(c.tp_w / max(int(mask.sum()), 1)))
        # uniform random dots, no hard core
        rng = np.random.default_rng(7)
        ys, xs = np.nonzero(domain)
        sel = rng.choice(len(ys), 37654, replace=False)
        mask = np.zeros(footprint.shape, bool)
        mask[ys[sel], xs[sel]] = True
        c = metric.dti_components(mask.astype(np.float32), truth_sgmc, valid=domain)
        ctrl["uniform_random_M37654"] = dict(
            M=37654, dti_sgmc=c.dti, mean_credit_per_dot=float(c.tp_w / 37654))

        sc = np.array([r["owner_reported_score"] for r in rows])
        d = np.array([r["dti_sgmc"] for r in rows])
        cr = np.array([r["mean_credit_per_dot"] for r in rows])
        rho, pv = spearmanr(d, sc)
        pr, ppv = pearsonr(d, sc)
        rho_c, pv_c = spearmanr(cr, sc)
        variant = dict(
            catalogue_buffer_px=buf,
            rows=rows, controls=ctrl,
            spearman_dti_vs_owner_score=dict(rho=float(rho), p=float(pv), n=int(len(rows))),
            pearson_dti_vs_owner_score=dict(r=float(pr), p=float(ppv)),
            spearman_credit_per_dot_vs_owner_score=dict(rho=float(rho_c), p=float(pv_c)),
        )
        if truth_cat is not None:
            dc = np.array([r["dti_catalogue"] for r in rows])
            rho2, pv2 = spearmanr(dc, sc)
            variant["spearman_dti_catalogue_vs_owner_score"] = dict(rho=float(rho2), p=float(pv2))
        report["variants"][f"buffer{buf}px"] = variant

    out = ROOT / "evidence" / "exp1_instrument_calibration.json"
    out.write_text(json.dumps(report, indent=1))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "rows"}
                      for k, v in report["variants"].items()}, indent=1))
    print("\nper-file (buffer 3 px):")
    for r in report["variants"]["buffer3px"]["rows"]:
        print(f"  {r['owner_reported_score']:.4f}  M={r['M']:7d}  dti_sgmc={r['dti_sgmc']:.4f}"
              f"  credit/dot={r['mean_credit_per_dot']:.4f}  cov={r['coverage']:.3f}  {r['file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
